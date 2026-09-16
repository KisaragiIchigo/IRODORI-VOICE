/**
 * VOICEVOX エディタへ IRODORI-VOICE 用の手を入れる。
 *
 * 当てる内容そのものは editor-patch-definitions.mjs が持つ。ここは宣言を順に当て、
 * --revert で本家の状態へ戻すことに専念する。上流の該当箇所が変わっていた場合は
 * 何もせずに終了する（当てずっぽうに置換して壊さないため）。
 *
 * 使い方:
 *   node tools/patch-editor.mjs            適用する
 *   node tools/patch-editor.mjs --revert   本家の状態へ戻す
 */

import { copyFileSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { relative } from "node:path";

import {
  additions,
  editorSrc,
  overrides,
  patches,
  root,
} from "./editor-patch-definitions.mjs";

const revert = process.argv.includes("--revert");


if (!existsSync(editorSrc)) {
  console.error("VOICEVOX エディタが見つかりません:");
  console.error(`  ${editorSrc}`);
  console.error("");
  console.error("先に setup-voicevox-editor.bat を実行してください。");
  process.exit(1);
}

let failed = false;

// --- 追加するファイル -------------------------------------------------------
for (const addition of additions) {
  if (revert) {
    if (existsSync(addition.to)) {
      rmSync(addition.to);
      console.log(`削除: ${relative(root, addition.to)}`);
    }
    continue;
  }
  if (!existsSync(addition.from)) {
    console.error(`追加元が見つかりません: ${relative(root, addition.from)}`);
    failed = true;
    continue;
  }
  copyFileSync(addition.from, addition.to);
  console.log(`配置: ${relative(root, addition.to)}`);
}

// --- 丸ごと差し替えるファイル -----------------------------------------------
for (const override of overrides) {
  const backup = `${override.to}.orig`;

  if (revert) {
    if (existsSync(backup)) {
      copyFileSync(backup, override.to);
      rmSync(backup);
      console.log(`書き戻し: ${relative(root, override.to)}`);
    }
    continue;
  }

  if (!existsSync(override.from)) {
    console.error(`差し替え元が見つかりません: ${relative(root, override.from)}`);
    failed = true;
    continue;
  }

  // 本家の中身は初回だけ退避する。適用済みの状態で上書きすると、退避側が
  // IRODORI-VOICE 版になって戻せなくなる。
  if (!existsSync(backup) && existsSync(override.to)) {
    copyFileSync(override.to, backup);
  }
  copyFileSync(override.from, override.to);
  console.log(`差し替え: ${relative(root, override.to)}`);
}

// --- 既存ファイルの置換 -----------------------------------------------------
for (const patch of patches) {
  if (!existsSync(patch.file)) {
    console.error(`${patch.name}: 対象のファイルがありません（${relative(root, patch.file)}）`);
    failed = true;
    continue;
  }

  const source = readFileSync(patch.file, "utf8");

  // 判定は必ず patched の有無で行う。patched が original を含む形（行の追加など）だと、
  // 適用済みでも original が見つかってしまい、同じ行を何度も足すことになる。
  const applied = source.includes(patch.patched);

  if (revert) {
    if (!applied) {
      console.log(`${patch.name}: 既に戻っています`);
      continue;
    }
    writeFileSync(patch.file, source.replace(patch.patched, patch.original), "utf8");
    console.log(`${patch.name}: ${relative(root, patch.file)} を戻しました。`);
    continue;
  }

  if (applied) {
    console.log(`${patch.name}: 既に適用済み`);
    continue;
  }

  if (!source.includes(patch.original)) {
    console.error(`${patch.name}: 対象の記述が見つかりません。上流の更新で変わった可能性があります。`);
    console.error(`  ${relative(root, patch.file)} を確認してください。`);
    failed = true;
    continue;
  }

  writeFileSync(patch.file, source.replace(patch.original, patch.patched), "utf8");
  console.log(`${patch.name}: ${relative(root, patch.file)} を更新しました。`);
}

console.log("");
if (failed) {
  console.error("一部を適用できませんでした。");
  process.exit(1);
}
if (revert) {
  console.log("本家の状態へ戻しました。");
} else {
  console.log("適用しました。エディタを起動し直すと反映されます。");
  console.log("  ・80〜300 文字の行で長文警告が出なくなります");
  console.log("  ・貼り付けたテキストが鉤括弧の中の句点では分割されなくなります");
  console.log("  ・メニューの「エンジン」→「音声モデルの管理」が増えます");
  console.log("  ・歌唱に対応した話者がいない間、ソングへの切り替えボタンが出なくなります");
  console.log("  ・ｱｸｾﾝﾄ欄の隣のｲﾝﾄﾈｰｼｮﾝ欄・長さ欄のタブが出なくなります");
  console.log("  ・起動時の更新確認が失敗しても、エラーとして記録されなくなります");
  console.log("  ・ヘルプの文面が IRODORI-VOICE のものになります");
  console.log("  ・辞書画面から辞書の書き出しと取り込みができるようになります");
  console.log("  ・既定テーマが「墨（くらい）」になります");
  console.log("    起動したことがある環境では保存済みの設定が優先されます。");
  console.log("    その場合は設定→テーマから選び直してください。");
}
