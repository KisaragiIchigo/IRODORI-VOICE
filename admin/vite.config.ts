import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // エンジンは /admin/ 配下でこの画面を配信する。先頭スラッシュの絶対パスで
  // 出力するとその配下に解決されないため、相対パスで吐かせる。
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // フォントは @fontsource を同梱する。外部 CDN を参照するとオフラインで壊れる。
    assetsInlineLimit: 0,
  },
  server: {
    port: 5174,
    proxy: {
      // 開発サーバーから叩くときだけエンジンへ中継する。
      // 本番は同一オリジンなので、この設定は効かない。
      "/api": "http://127.0.0.1:50121",
    },
  },
});
