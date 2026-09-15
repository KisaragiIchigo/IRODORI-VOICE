/**
 * IRODORI VOICE の配色。
 *
 * VOICEVOX の既定は淡い緑を基調にしている。こちらは京都の石畳と和傘から採った
 * 4 色で組む。色は project_style.json の palette と対応させている。
 *
 *   紅   #B94047 … 和傘。アクセント
 *   常磐 #2F4F2F … 苔と木立。落ち着いた対比
 *   白茶 #D2B48C … 土塀。注意と補助
 *   白練 #F8F8FF … 明るい面と文字
 *
 * VOICEVOX エディタの src/domain/theme/index.ts へ差し込んで使う。
 * 変更するのはこのファイルの追記と、末尾の themes 配列の 1 行のみ。
 */

import type { ThemeConf } from "@/type/preload";

/** 彩（いろどり）… 白練の地に紅を差す。雨上がりの石畳の明るさ。 */
const irodoriLight = {
  name: "IrodoriLight",
  displayName: "彩（あかるい）",
  order: 3,
  isDark: false,
  colors: {
    // 紅。project_style.json の accent_solid。
    primary: "#B94047",
    // 常磐を落とした墨緑。真っ黒より地に馴染む。
    display: "#1F2A20",
    "display-on-primary": "#F8F8FF",
    // 常磐。リンクは下線が付くため、青でなくても迷わない。
    "display-hyperlink": "#2F4F2F",
    // 白練。
    background: "#F8F8FF",
    surface: "#EDEEF6",
    // 紅を濃くしたもの。primary と並んでも区別できる暗さにする。
    warning: "#8A2B33",
    // 白茶の淡色。
    "text-splitter-hover": "#EFE3D2",
    "active-point-focus": "#F5E2E3",
    "active-point-hover": "#FAF0F1",
  },
} as const satisfies ThemeConf;

/** 墨（すみ）… 夜の作業机。project_style.json の既定配色をそのまま使う。 */
const irodoriDark = {
  name: "IrodoriDark",
  displayName: "墨（くらい）",
  order: 4,
  isDark: true,
  colors: {
    // 紅。
    primary: "#B94047",
    // 白練。
    display: "#F8F8FF",
    "display-on-primary": "#F8F8FF",
    // 常磐を持ち上げたもの。暗い地でも沈まない明度にする。
    "display-hyperlink": "#A3C9A3",
    // 墨。base_bg。常磐の色相を残したまま明度を落としてある。
    background: "#0E1210",
    surface: "#18201A",
    // 白茶。暗い地ではこれが一番よく目に留まる。
    warning: "#D2B48C",
    // 白茶と紅の、地に沈めた派生。
    "text-splitter-hover": "#2A241C",
    "active-point-focus": "#2E1A1C",
    "active-point-hover": "#221416",
  },
} as const satisfies ThemeConf;

export const irodoriThemes = [irodoriLight, irodoriDark];
