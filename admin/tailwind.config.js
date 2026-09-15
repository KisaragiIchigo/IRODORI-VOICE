/** @type {import('tailwindcss').Config} */

// 色とフォントの出どころはプロジェクトルートの project_style.json。
// ここに無い値を JSX へ直書きしないこと。追加するときは先にマニフェストを更新する。
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 地。白練の対極として、常磐の色相を残したまま明度を落とした墨。
        ground: {
          DEFAULT: "#0e1210",
          deep: "#080b09",
        },
        // 紅。和傘の色。アクセントはこの一系統だけに絞る。
        beni: {
          DEFAULT: "#b94047",
          mid: "#a3373e",
          deep: "#8a2b33",
          pale: "#e79aa0",
        },
        // 常磐。そろった・使える状態を示す。暗い地では文字に pale を使う。
        tokiwa: {
          DEFAULT: "#2f4f2f",
          mid: "#3f6b3f",
          light: "#6fa06f",
          pale: "#a3c9a3",
        },
        // 白茶。足りない・任意を示すところと、数値の強調に使う。
        shiracha: {
          DEFAULT: "#d2b48c",
          deep: "#a98a64",
          pale: "#e6d2b5",
        },
        // 白練からの階調。文字はここだけを使う。500 はプレースホルダ専用。
        paper: {
          DEFAULT: "#f8f8ff",
          100: "#f8f8ff",
          200: "#e6e7f0",
          300: "#c6c9d5",
          400: "#9a9eac",
          500: "#6c7080",
        },
        // 話者の識別色。8 人を見分けるため色相を散らす。基調の 4 色とは別のレイヤー。
        voice: {
          shu: "#b94047",
          yamabuki: "#e0a13a",
          wakatake: "#66b070",
          asagi: "#3fa4b8",
          rurikon: "#5a72c9",
          fuji: "#9a76d0",
          kobai: "#dd6f95",
          sumire: "#7c86a8",
        },
      },
      fontFamily: {
        display: ["Archivo", "M PLUS 1", "sans-serif"],
        sans: ["M PLUS 1", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      fontSize: {
        // リサイズに滑らかに追従させる。刻みは project_style.json の fluid に従う。
        label: ["clamp(0.6875rem, 0.66rem + 0.14vw, 0.8125rem)", { lineHeight: "1.4" }],
        body: ["clamp(0.8125rem, 0.78rem + 0.16vw, 0.9375rem)", { lineHeight: "1.7" }],
        title: ["clamp(1rem, 0.92rem + 0.4vw, 1.375rem)", { lineHeight: "1.35" }],
        hero: ["clamp(1.25rem, 1.05rem + 0.9vw, 1.875rem)", { lineHeight: "1.2" }],
      },
      boxShadow: {
        glow: "0 0 16px rgba(185,64,71,0.25)",
        inset: "inset 0 1px 3px rgba(0,0,0,0.5)",
      },
      keyframes: {
        // 処理中の行に置く呼吸。派手に動かすと作業の邪魔になる。
        breathe: {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
        // 手前へ立ち上がるパネル。跳ねさせず、止まる瞬間だけ減速させる。
        "dialog-in": {
          from: { opacity: "0", transform: "translate(-50%, -50%) translateY(10px) scale(0.985)" },
          to: { opacity: "1", transform: "translate(-50%, -50%)" },
        },
        // 背後を沈める幕。
        "veil-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        breathe: "breathe 2.4s ease-in-out infinite",
        "dialog-in": "dialog-in 200ms cubic-bezier(0.16, 1, 0.3, 1)",
        "veil-in": "veil-in 150ms ease-out",
      },
    },
  },
  plugins: [],
};
