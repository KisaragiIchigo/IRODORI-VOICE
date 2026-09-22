/**
 * 読み方＆アクセント辞書へ登録した語を、フレーズ分割辞書へも通す。
 *
 * エンジンは辞書の読みを「語の切れ目」に限って当てる。切れ目は形態素解析が決めるため、
 * 解析が 1 語として切る複合語（「証券取引所」）の内側へ登録した語（「取引所」）は、
 * 優先度を上げても当たらないことがある。フレーズ分割辞書で区切りを入れておくと、その
 * 位置が切れ目になり、登録した読みが当たるようになる。
 *
 * そこで登録語を ``取引所=_取引所_`` の形で分割辞書へも入れる。アンダースコアは「間を
 * 空けずにアクセント句だけを分ける」区切りなので、ポーズは増えずに語の前後が切れ目に
 * なる。
 *
 * エンジンには 1 語だけを足す口が無く、送った一覧がそのまま辞書になる。ここは手元の
 * 一覧へ足し引きした結果を組むだけの純粋な計算で、やり取りは呼ぶ側が行う。
 */

import type { WordSplits } from "@/domain/wordSplits";

/**
 * 利用者が「間を空けずに区切る」意図で書く文字。エンジンと同じ並び。
 *
 * 半角空白・全角空白・アンダースコア・全角アンダースコアの 4 つ。エンジンはこれらを
 * すべて同じ区切りとして扱うため、書いた形が違っても同じ登録と見なせるようにする。
 */
const MARKER_SOURCES = [" ", "　", "_", "＿"];

/** 区切りの字をマーカーへ畳む。エンジンの ``_fold_markers`` と同じ処理。 */
const foldMarkers = (value: string): string =>
  MARKER_SOURCES.reduce(
    (folded, source) => folded.split(source).join("|"),
    value,
  );

/** 同時登録で書き込む分割後の文字列。 */
export const autoSplitValue = (surface: string): string => `_${surface}_`;

/**
 * 分割後の文字列が、同時登録で書いたそのままの形かどうか。
 *
 * 手で区切りを足した内容（「台湾証券_取引所」）と、同時登録が書いた形（「_台湾証券取引所_」）
 * を見分けるために使う。区切りの字は書き手によって空白とアンダースコアが混ざるため、
 * エンジンと同じくマーカーへ畳んでから比べる。
 */
export const isAutoSplitValue = (
  surface: string,
  value: string | undefined,
): boolean => value != undefined && foldMarkers(value) === `|${surface}|`;

/** その語が分割辞書へ登録されているか。 */
export const isSplitRegistered = (
  splits: WordSplits,
  surface: string,
): boolean => surface in splits;

/**
 * 語の登録・変更・削除に合わせた分割辞書を組む。変更が要らなければ ``undefined``。
 *
 * - 登録する側に倒したとき、まだ無ければ ``_単語_`` を足す。既にあるものは触らない。
 *   手で区切りを直した内容を、同時登録が書き戻して消さないため。
 * - 登録しない側に倒したときは、その語の登録を消す。利用者がその語について明示的に
 *   外した操作なので、手で直した内容でも意図どおりに消える。
 * - 表記を変えたときは、前の表記の登録が同時登録のままの形なら消す。手で直した内容は
 *   残す。表記に合わせて書き換えると、利用者が組んだ区切りが黙って消えるため。
 */
export const planSplitLink = (params: {
  splits: WordSplits;
  /** 変更前の表記。新しい語の登録では渡さない。 */
  previousSurface?: string;
  surface: string;
  registered: boolean;
}): WordSplits | undefined => {
  const { splits, previousSurface, surface, registered } = params;
  const next = { ...splits };
  let changed = false;

  if (
    previousSurface != undefined &&
    previousSurface !== surface &&
    isAutoSplitValue(previousSurface, next[previousSurface])
  ) {
    delete next[previousSurface];
    changed = true;
  }

  if (registered) {
    if (!(surface in next)) {
      next[surface] = autoSplitValue(surface);
      changed = true;
    }
  } else if (surface in next) {
    delete next[surface];
    changed = true;
  }

  return changed ? next : undefined;
};

/**
 * 語を削除したあとの分割辞書を組む。変更が要らなければ ``undefined``。
 *
 * 消すのは同時登録が書いたままの形だけ。手で区切りを直した内容は、読み方の登録を
 * 消したあとも分割としては役に立つため残す。
 */
export const planSplitUnlink = (params: {
  splits: WordSplits;
  surface: string;
}): WordSplits | undefined => {
  const { splits, surface } = params;
  if (!isAutoSplitValue(surface, splits[surface])) return undefined;

  const next = { ...splits };
  delete next[surface];
  return next;
};
