/**
 * 辞書一覧の絞り込み。
 *
 * 読み方＆アクセント辞書とフレーズ分割辞書の両方から使う。語が増えると一覧を目で
 * 追えなくなるため、入力した文字で候補を絞る。どの欄を照合に使うかは呼ぶ側が決め、
 * ここは「与えられた文字列のどれかに当たるか」だけを判定する。
 *
 * 照合は 2 通り。
 *
 *   テキスト   入力を含む欄があれば当たり。全角と半角、大小文字、ひらがなとカタカナの
 *              違いを吸収する。「らくてん」で読み「ラクテン」が、「gui」で表記「ＧＵＩ」が
 *              見つかる。
 *   正規表現   入力をそのまま正規表現として扱う。書き損じは例外にせず、理由を返して
 *              画面に出させる（入力途中の「(」で一覧が消えないようにするため）。
 */

import { convertHiraToKana } from "@/domain/japanese";

/** 照合のしかた。 */
export type DictSearchMode = "text" | "regex";

/** 組み立てた照合器。正規表現の書き損じは ``error`` として返る。 */
export type DictMatcher =
  | {
      readonly type: "matcher";
      /** 与えた欄のどれかに当たれば ``true``。入力が空なら常に ``true``。 */
      readonly matches: (fields: readonly string[]) => boolean;
    }
  | { readonly type: "error"; readonly message: string };

/**
 * 照合に使う形へ畳む。
 *
 * NFKC で全角英数を半角へ寄せ、小文字へ落とし、ひらがなをカタカナへ寄せる。読みは
 * カタカナで保存される一方、打つのはひらがなのほうが速いため。
 */
const fold = (text: string): string =>
  convertHiraToKana(text.normalize("NFKC").toLowerCase());

/** 正規表現の照合に使う形。入力をそのまま扱うため、畳んだ形と素の形の両方を試す。 */
const regexTargets = (field: string): readonly string[] => {
  const folded = fold(field);
  return folded === field ? [field] : [field, folded];
};

/**
 * 入力から照合器を組み立てる。
 *
 * 呼ぶ側は毎キー入力で呼ぶため、正規表現のコンパイルはここで 1 度だけ行い、
 * 判定関数を閉じ込めて返す。
 */
export const createDictMatcher = (
  query: string,
  mode: DictSearchMode,
): DictMatcher => {
  const trimmed = query.trim();
  if (trimmed === "") {
    return { type: "matcher", matches: () => true };
  }

  if (mode === "regex") {
    let pattern: RegExp;
    try {
      // u フラグは付けない。付けると「\d」以外の素朴な書き方（「\-」など）まで
      // 例外になり、検索のために正規表現の作法を覚える必要が出てしまう。
      pattern = new RegExp(trimmed, "i");
    } catch (e) {
      return {
        type: "error",
        message: e instanceof Error ? e.message : "正規表現として読めません。",
      };
    }
    return {
      type: "matcher",
      matches: (fields) =>
        fields.some((field) =>
          regexTargets(field).some((target) => pattern.test(target)),
        ),
    };
  }

  const needle = fold(trimmed);
  return {
    type: "matcher",
    matches: (fields) => fields.some((field) => fold(field).includes(needle)),
  };
};
