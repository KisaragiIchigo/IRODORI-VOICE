import { describe, expect, it } from "vitest";
import { createDictMatcher } from "@/domain/dictSearch";

/** 照合器を組んで、当たりだけを返す。 */
const filter = (
  query: string,
  mode: "text" | "regex",
  rows: readonly (readonly string[])[],
) => {
  const matcher = createDictMatcher(query, mode);
  if (matcher.type !== "matcher") throw new Error(matcher.message);
  return rows.filter((row) => matcher.matches(row));
};

describe("createDictMatcher（テキスト）", () => {
  const rows = [
    ["台湾証券取引所", "タイワンショウケントリヒキショ"],
    ["ＧＵＩ", "グイ"],
    ["楽天モバイル", "ラクテンモバイル"],
  ];

  it("入力が空なら全部当たる", () => {
    expect(filter("", "text", rows)).toHaveLength(3);
  });

  it("表記の一部で当たる", () => {
    expect(filter("取引", "text", rows)).toEqual([rows[0]]);
  });

  it("読みの一部で当たる", () => {
    expect(filter("トリヒキ", "text", rows)).toEqual([rows[0]]);
  });

  it("ひらがなで打っても読みに当たる", () => {
    expect(filter("らくてん", "text", rows)).toEqual([rows[2]]);
  });

  it("半角で打っても全角の表記に当たる", () => {
    expect(filter("gui", "text", rows)).toEqual([rows[1]]);
  });

  it("前後の空白は無視する", () => {
    expect(filter("  取引  ", "text", rows)).toEqual([rows[0]]);
  });

  it("当たらない入力では空になる", () => {
    expect(filter("該当なし", "text", rows)).toEqual([]);
  });
});

describe("createDictMatcher（正規表現）", () => {
  const rows = [
    ["台湾証券取引所", "タイワンショウケントリヒキショ"],
    ["ＧＵＩ", "グイ"],
    ["楽天モバイル", "ラクテンモバイル"],
  ];

  it("行頭と行末の指定が効く", () => {
    expect(filter("^楽天", "regex", rows)).toEqual([rows[2]]);
    expect(filter("所$", "regex", rows)).toEqual([rows[0]]);
  });

  it("選択の指定が効く", () => {
    expect(filter("取引所|モバイル", "regex", rows)).toEqual([
      rows[0],
      rows[2],
    ]);
  });

  it("全角の表記も畳んだ形で当たる", () => {
    expect(filter("^gui$", "regex", rows)).toEqual([rows[1]]);
  });

  it("書き損じは例外にせず理由を返す", () => {
    const matcher = createDictMatcher("(未閉じ", "regex");
    expect(matcher.type).toBe("error");
  });

  it("テキストとして扱えば記号はそのまま照合できる", () => {
    const symbols = [["(株)", "カブシキガイシャ"]];
    expect(filter("(株)", "text", symbols)).toEqual([symbols[0]]);
  });
});
