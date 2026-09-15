import { describe, expect, it } from "vitest";
import { splitTextByPeriodAndNewLine } from "@/domain/irodoriTextSplit";

describe("splitTextByPeriodAndNewLine", () => {
  it("句点の後ろで分割する", () => {
    expect(splitTextByPeriodAndNewLine("あ。い。")).toEqual([
      "あ。",
      "い。",
      "",
    ]);
  });

  it("鉤括弧の中の句点では分割しない", () => {
    expect(splitTextByPeriodAndNewLine("「あ。い」う。")).toEqual([
      "「あ。い」う。",
      "",
    ]);
  });

  it("閉じ括弧の後ろの句点では分割する", () => {
    expect(
      splitTextByPeriodAndNewLine(
        "「ホチキス留め：必ず1枚目の向き・上下を目視確認。左上斜め留め」。次の話。",
      ),
    ).toEqual([
      "「ホチキス留め：必ず1枚目の向き・上下を目視確認。左上斜め留め」。",
      "次の話。",
      "",
    ]);
  });

  it("閉じ括弧が無い開き括弧は囲みとして扱わない", () => {
    expect(splitTextByPeriodAndNewLine("「あ。い。")).toEqual([
      "「あ。",
      "い。",
      "",
    ]);
  });

  it("二重鉤括弧の入れ子を囲みとして扱う", () => {
    expect(
      splitTextByPeriodAndNewLine("「彼は『行く。』と言った。」次の話。"),
    ).toEqual(["「彼は『行く。』と言った。」次の話。", ""]);
  });

  it("括弧の中でも改行では分割する", () => {
    expect(splitTextByPeriodAndNewLine("「あ。\nい」う。")).toEqual([
      "「あ。",
      "い」う。",
      "",
    ]);
  });

  it("CRLF と LF のどちらでも分割する", () => {
    expect(splitTextByPeriodAndNewLine("あ。\r\nい\nう")).toEqual([
      "あ。",
      "",
      "い",
      "う",
    ]);
  });

  it("空文字列はそのまま返す", () => {
    expect(splitTextByPeriodAndNewLine("")).toEqual([""]);
  });
});
