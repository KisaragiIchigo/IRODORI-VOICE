/**
 * ビルドしたエンジンをエディタから自動起動させる。
 *
 * build-engine.bat でエンジンを exe にまとめた後にこれを実行すると、
 * .env の executionEnabled が true になり、エディタを起動するだけで
 * エンジンも一緒に立ち上がるようになる（手動で 2 つ起動しなくて済む）。
 *
 * 使い方:
 *   node tools/enable-auto-engine.mjs            有効にする
 *   node tools/enable-auto-engine.mjs --disable  手動起動へ戻す
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const toolsDir = dirname(fileURLToPath(import.meta.url));
const root = dirname(toolsDir);
const disable = process.argv.includes("--disable");

const enginePath = join(
  root,
  "engine",
  "dist",
  "irodori-voice-engine",
  "irodori-voice-engine.exe",
);
const templatePath = join(root, "voicevox-editor.env.template");
const editorEnvPath = join(root, "editor-voicevox", ".env");

if (!disable && !existsSync(enginePath)) {
  console.error("エンジンの実行ファイルが見つかりません:");
  console.error(`  ${enginePath}`);
  console.error("");
  console.error("先に build-engine.bat を実行してください。");
  process.exit(1);
}

/** .env の該当行だけを書き換える。他の設定には触れない。 */
function apply(path) {
  if (!existsSync(path)) {
    console.log(`  ${path} が無いため省略しました。`);
    return;
  }

  let source = readFileSync(path, "utf8");

  if (disable) {
    source = source
      .replace(/"executionEnabled":\s*true/, '"executionEnabled": false')
      .replace(/"executionFilePath":\s*"[^"]*"/, '"executionFilePath": ""');
  } else {
    // .env は JSON をバッククォートで囲んで書くため、パスの区切りをエスケープする。
    const escaped = enginePath.replace(/\\/g, "\\\\");
    source = source
      .replace(/"executionEnabled":\s*false/, '"executionEnabled": true')
      .replace(/"executionFilePath":\s*"[^"]*"/, `"executionFilePath": "${escaped}"`);
  }

  writeFileSync(path, source, "utf8");
  console.log(`  ${relative(root, path)} を更新しました。`);
}

apply(templatePath);
apply(editorEnvPath);

console.log("");
if (disable) {
  console.log("エンジンの自動起動を無効にしました。");
  console.log("start-engine.bat で手動起動してから、エディタを起動してください。");
} else {
  console.log("エンジンの自動起動を有効にしました。");
  console.log("start-voicevox-editor.bat だけでエンジンも一緒に立ち上がります。");
}
