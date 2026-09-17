/**
 * フレーズ分割辞書の読み書き。
 *
 * 長い複合語をひと塊のまま渡すとモデルが読みを外すため、「ここで区切る」と決めた
 * 位置を表記の側で伝えるための辞書。外部ツールから届いたテキストへ、エンジンが
 * 合成の直前に当てる。
 *
 * ここが受け持つのはエンジンとのやり取りと、取り込むファイルが辞書の形をして
 * いるかの確認まで。区切りの意味づけ（読点なら間を空ける、アンダースコアなら
 * アクセント句だけを分ける）はエンジンが持つ。
 */

import type { EngineInfo } from "@/type/preload";

/** 登録した分割の一覧。鍵が変換前の単語、値が分割後の文字列。 */
export type WordSplits = Record<string, string>;

/** 分割辞書の入口。 */
const wordSplitsUrl = (engine: EngineInfo): string => {
  const port = engine.defaultPort ? `:${engine.defaultPort}` : "";
  return `${engine.protocol}//${engine.hostname}${port}${engine.pathname}/word_splits`;
};

/** 登録済みの分割を取り出す。 */
export const fetchWordSplits = async (
  engine: EngineInfo,
): Promise<WordSplits> => {
  const response = await fetch(wordSplitsUrl(engine), { method: "GET" });
  if (!response.ok) {
    throw new Error(
      `エンジンから分割辞書を取り出せませんでした（HTTP ${response.status}）。`,
    );
  }
  return (await response.json()) as WordSplits;
};

/**
 * 分割辞書を丸ごと入れ替える。
 *
 * 1 語だけを足す口はエンジンに無く、送った一覧がそのまま辞書になる。呼ぶ側は
 * 手元の一覧へ足し引きしてから渡す。
 */
export const sendWordSplits = async (
  engine: EngineInfo,
  splits: WordSplits,
): Promise<void> => {
  const response = await fetch(wordSplitsUrl(engine), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(splits),
  });
  if (!response.ok) {
    throw new Error(
      `エンジンが分割辞書を受け取れませんでした（HTTP ${response.status}）。`,
    );
  }
};

/**
 * 読み込んだファイルを、エンジンへ渡せる形か確かめて返す。
 *
 * 選び間違えたファイルをそのままエンジンへ送ると、返ってくるのは検証の
 * エラーだけで、どこが悪いのかは利用者に伝わらない。選んだ直後に日本語で
 * 伝わるほうが早い。
 */
export const readWordSplitsFile = (text: string): WordSplits => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text.trim());
  } catch {
    throw new Error("JSON として読めないファイルです。");
  }
  if (typeof parsed !== "object" || parsed == null || Array.isArray(parsed)) {
    throw new Error("分割辞書の中身が、単語の一覧になっていません。");
  }
  const entries = Object.entries(parsed);
  if (entries.length === 0) {
    throw new Error("分割辞書に単語が 1 つも入っていません。");
  }
  for (const [target, replacement] of entries) {
    if (typeof replacement !== "string") {
      throw new Error(
        `「${target}」の分割後の文字列が、文字列ではありません。`,
      );
    }
  }
  return Object.fromEntries(entries);
};
