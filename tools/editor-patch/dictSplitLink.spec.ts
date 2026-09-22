import { describe, expect, it } from "vitest";
import {
  autoSplitValue,
  isAutoSplitValue,
  isSplitRegistered,
  planSplitLink,
  planSplitUnlink,
} from "@/domain/dictSplitLink";

describe("autoSplitValue / isAutoSplitValue", () => {
  it("同時登録は語をアンダースコアで囲んだ形になる", () => {
    expect(autoSplitValue("取引所")).toBe("_取引所_");
  });

  it("書いたままの形を同時登録と見なす", () => {
    expect(isAutoSplitValue("取引所", "_取引所_")).toBe(true);
  });

  it("区切りの字が空白でも同時登録と見なす", () => {
    expect(isAutoSplitValue("取引所", " 取引所 ")).toBe(true);
    expect(isAutoSplitValue("取引所", "　取引所＿")).toBe(true);
  });

  it("手で区切りを足した内容は同時登録と見なさない", () => {
    expect(isAutoSplitValue("台湾証券取引所", "台湾証券_取引所")).toBe(false);
    expect(isAutoSplitValue("取引所", "取引所")).toBe(false);
    expect(isAutoSplitValue("取引所", undefined)).toBe(false);
  });
});

describe("isSplitRegistered", () => {
  it("登録の有無を返す", () => {
    const splits = { 取引所: "_取引所_" };
    expect(isSplitRegistered(splits, "取引所")).toBe(true);
    expect(isSplitRegistered(splits, "証券")).toBe(false);
  });
});

describe("planSplitLink", () => {
  it("新しい語を登録すると分割も足される", () => {
    expect(
      planSplitLink({ splits: {}, surface: "取引所", registered: true }),
    ).toEqual({ 取引所: "_取引所_" });
  });

  it("既にある分割は書き換えない", () => {
    expect(
      planSplitLink({
        splits: { 台湾証券取引所: "台湾証券_取引所" },
        previousSurface: "台湾証券取引所",
        surface: "台湾証券取引所",
        registered: true,
      }),
    ).toBeUndefined();
  });

  it("登録を外すと分割が消える", () => {
    expect(
      planSplitLink({
        splits: { 取引所: "_取引所_", 証券: "_証券_" },
        previousSurface: "取引所",
        surface: "取引所",
        registered: false,
      }),
    ).toEqual({ 証券: "_証券_" });
  });

  it("登録を外すと手で直した分割も消える", () => {
    expect(
      planSplitLink({
        splits: { 台湾証券取引所: "台湾証券_取引所" },
        previousSurface: "台湾証券取引所",
        surface: "台湾証券取引所",
        registered: false,
      }),
    ).toEqual({});
  });

  it("表記を変えると同時登録の分割も付いて移る", () => {
    expect(
      planSplitLink({
        splits: { 取引所: "_取引所_" },
        previousSurface: "取引所",
        surface: "証券取引所",
        registered: true,
      }),
    ).toEqual({ 証券取引所: "_証券取引所_" });
  });

  it("表記を変えても手で直した分割は残す", () => {
    expect(
      planSplitLink({
        splits: { 台湾証券取引所: "台湾証券_取引所" },
        previousSurface: "台湾証券取引所",
        surface: "台湾証券取引所（旧）",
        registered: true,
      }),
    ).toEqual({
      台湾証券取引所: "台湾証券_取引所",
      "台湾証券取引所（旧）": "_台湾証券取引所（旧）_",
    });
  });

  it("登録しない語では何も起きない", () => {
    expect(
      planSplitLink({ splits: {}, surface: "取引所", registered: false }),
    ).toBeUndefined();
  });
});

describe("planSplitUnlink", () => {
  it("同時登録の分割は語の削除に付いて消える", () => {
    expect(
      planSplitUnlink({ splits: { 取引所: "_取引所_" }, surface: "取引所" }),
    ).toEqual({});
  });

  it("手で直した分割は語を削除しても残す", () => {
    expect(
      planSplitUnlink({
        splits: { 台湾証券取引所: "台湾証券_取引所" },
        surface: "台湾証券取引所",
      }),
    ).toBeUndefined();
  });

  it("登録が無ければ何も起きない", () => {
    expect(planSplitUnlink({ splits: {}, surface: "取引所" })).toBeUndefined();
  });
});
