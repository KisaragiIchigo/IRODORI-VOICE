/**
 * 読み方＆アクセント辞書の書き出しと取り込み。
 *
 * ファイルの形は AivisSpeech が書き出すものに合わせてある。同じ語を両方のソフトで
 * 使い回せるようにするためで、AivisSpeech から出したファイルをそのまま読めるし、
 * ここから出したファイルを AivisSpeech でも読める。
 *
 * 形を合わせる仕事はエンジンが持つ。品詞ごとの文脈 ID は辞書のビルドが通るかどうかに
 * 直結し、正しい値を知っているのは辞書を組み立てるエンジンだけなので、ここでは
 * ファイルの入出力と、エンジンとのやり取りだけを受け持つ。
 */

import type { EngineInfo } from "@/type/preload";

/** 取り込みの結果。エンジンが数えて返す。 */
export type AivisDictImportSummary = {
  /** 取り込めた語数。 */
  imported: number;
  /** 受け取れなかった語と、その理由。 */
  skipped: string[];
  /** 取り込み後に辞書へ入っている語数。 */
  total: number;
  /** 辞書を読み上げへ反映できなかった場合の理由。 */
  error: string | null;
};

/** 辞書ファイルの入口。 */
const aivisDictUrl = (engine: EngineInfo): string => {
  const port = engine.defaultPort ? `:${engine.defaultPort}` : "";
  return `${engine.protocol}//${engine.hostname}${port}${engine.pathname}/user_dict/aivis`;
};

/** 書き出すファイルの既定の名前。同じ日に何度出しても迷わないよう日付を入れる。 */
export const defaultAivisDictFileName = (now: Date): string => {
  const stamp = [
    now.getFullYear(),
    `${now.getMonth() + 1}`.padStart(2, "0"),
    `${now.getDate()}`.padStart(2, "0"),
  ].join("");
  return `${stamp} IRODORI-VOICE辞書.json`;
};

/** 辞書をファイルの形で取り出す。 */
export const fetchAivisDictFile = async (
  engine: EngineInfo,
): Promise<string> => {
  const response = await fetch(aivisDictUrl(engine), { method: "GET" });
  if (!response.ok) {
    throw new Error(
      `エンジンから辞書を取り出せませんでした（HTTP ${response.status}）。`,
    );
  }
  // 字下げは AivisSpeech が書くファイルと同じ 4 つ。テキストのまま差分を取れる形にしておくと、
  // どの語が増えたのかを他のソフトを開かずに追える。
  return `${JSON.stringify(await response.json(), undefined, 4)}\n`;
};

/**
 * 読み込んだファイルを、エンジンへ渡せる形か確かめて文字列にする。
 *
 * 中身の細かい検査はエンジンが行う。ここで見るのは、そもそも JSON として読めるか、
 * 単語の一覧の形をしているかまで。選び間違えたファイルをエンジンへ送って
 * 英語のエラーを見せるより、選んだ直後に日本語で伝わるほうが早い。
 */
export const readAivisDictFile = (bytes: Uint8Array): string => {
  const text = new TextDecoder("utf-8").decode(bytes).trim();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("JSON として読めないファイルです。");
  }
  if (typeof parsed !== "object" || parsed == null || Array.isArray(parsed)) {
    throw new Error("辞書ファイルの中身が、単語の一覧になっていません。");
  }
  if (Object.keys(parsed).length === 0) {
    throw new Error("辞書ファイルに単語が 1 つも入っていません。");
  }
  return text;
};

/** 辞書ファイルの中身をエンジンへ渡す。同じ識別子の語は読み込んだ側で上書きする。 */
export const sendAivisDictFile = async (
  engine: EngineInfo,
  contents: string,
): Promise<AivisDictImportSummary> => {
  const response = await fetch(`${aivisDictUrl(engine)}?override=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: contents,
  });
  if (!response.ok) {
    throw new Error(
      `エンジンが辞書を受け取れませんでした（HTTP ${response.status}）。`,
    );
  }
  return (await response.json()) as AivisDictImportSummary;
};

/** 取り込みの結果を、利用者へ見せる文面にまとめる。 */
export const describeImportSummary = (
  summary: AivisDictImportSummary,
): string => {
  const lines = [
    `${summary.imported} 語を取り込みました。辞書の語数は ${summary.total} 語です。`,
  ];
  if (summary.skipped.length > 0) {
    lines.push("", `次の ${summary.skipped.length} 語は取り込めませんでした。`);
    // 全部並べると画面に収まらないため、先頭だけを出して残りは数で伝える。
    lines.push(...summary.skipped.slice(0, 10).map((reason) => `・${reason}`));
    if (summary.skipped.length > 10) {
      lines.push(`・ほか ${summary.skipped.length - 10} 語`);
    }
  }
  if (summary.error) {
    lines.push(
      "",
      `ただし、読み上げへの反映でつまずいています。${summary.error}`,
    );
  }
  return lines.join("\n");
};
