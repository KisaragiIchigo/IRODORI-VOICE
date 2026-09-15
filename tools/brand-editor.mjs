/**
 * VOICEVOX エディタを IRODORI VOICE として動かすための書き換え。
 *
 * 触るのは次の 3 か所だけ。それ以外のソースには手を入れないため、
 * editor-voicevox/ で git pull すれば上流の更新をそのまま取り込める。
 *
 *   1. package.json の "name"
 *        VOICEVOX の vite.config.ts が VITE_APP_NAME との一致を検証する。
 *        Electron のユーザーデータ保存先にもなるため、エンジンが使う
 *        %APPDATA%/IRODORI-VOICE と衝突しないよう -editor を付ける
 *        （Windows は大文字小文字を区別しないため irodori-voice だと同一になる）。
 *
 *   2. build/electronBuilderConfig.ts の productName
 *        配布物とウィンドウに出るアプリ名。
 *
 *   3. src/domain/theme/index.ts へ和風テーマを追加
 *        VOICEVOX の既定は淡い緑基調。京都の石畳と和傘から採った 4 色を足す。
 *
 *   4. public/icon.png を差し替え
 *        タイトルバーの左に出るアイコンで、配布した exe のアイコンにもなる
 *        （electronBuilderConfig.ts の win / linux がこのファイルを指している）。
 *
 *   5. タイトルバーとアプリメニューの表示名
 *        "VOICEVOX" がソースへ直接書かれている箇所を差し替える。
 */

import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const APP_NAME = "irodori-voice-editor";
const PRODUCT_NAME = "IRODORI VOICE";
const THEME_IMPORT = `import { irodoriThemes } from "./irodori";`;
const TITLE_NAME = "IRODORI VOICE";

/** タイトルバーとアプリメニューに出る名前。ソースへ直接書かれている。 */
const titleTargets = [
  {
    label: "タイトルバー",
    file: ["src", "components", "Menu", "MenuBar", "MenuBar.vue"],
    original: '    "VOICEVOX" +',
    patched: `    "${TITLE_NAME}" +`,
  },
  {
    label: "初回起動画面のタイトルバー",
    file: ["src", "welcome", "components", "MenuBar.vue"],
    original: '    "VOICEVOX" +',
    patched: `    "${TITLE_NAME}" +`,
  },
  {
    label: "アプリメニュー（macOS）",
    file: ["src", "backend", "electron", "main.ts"],
    original: '    label: "VOICEVOX",',
    patched: `    label: "${TITLE_NAME}",`,
  },
  {
    // タスクバーとウィンドウのタイトル。画面内の表示が入るまでのあいだ、これが出る。
    label: "ウィンドウのタイトル",
    file: ["src", "index.html"],
    original: "<title>VOICEVOX</title>",
    patched: `<title>${TITLE_NAME}</title>`,
  },
  {
    // 版の数字は上流の開発版そのまま（999.999.999）で、利用者には意味がない。
    label: "版の表記",
    file: ["src", "components", "Menu", "MenuBar", "MenuBar.vue"],
    original: '    (" - Ver. " + getAppInfos().version) +\n',
    patched: "",
  },
  {
    label: "版の表記（import）",
    file: ["src", "components", "Menu", "MenuBar", "MenuBar.vue"],
    original: 'import { getAppInfos } from "@/domain/appInfo";\n',
    patched: "",
  },
  {
    label: "版の表記（初回起動画面）",
    file: ["src", "welcome", "components", "MenuBar.vue"],
    original: '    (" - Ver. " + getAppInfos().version) +\n',
    patched: "",
  },
  {
    label: "版の表記（初回起動画面の import）",
    file: ["src", "welcome", "components", "MenuBar.vue"],
    original: 'import { getAppInfos } from "@/domain/appInfo";\n',
    patched: "",
  },
];

const toolsDir = dirname(fileURLToPath(import.meta.url));
const editorDir = process.argv[2];

if (!editorDir) {
  console.error("使い方: node brand-editor.mjs <エディタのディレクトリ>");
  process.exit(1);
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

/** package.json の name を差し替える。整形や他のフィールドには触れない。 */
function applyPackageName() {
  const path = join(editorDir, "package.json");
  if (!existsSync(path)) fail(`package.json が見つかりません: ${path}`);

  const source = readFileSync(path, "utf8");
  const current = JSON.parse(source).name;
  if (current === APP_NAME) {
    console.log(`package.json の name は既に ${APP_NAME} です。`);
    return;
  }

  const replaced = source.replace(/("name":\s*)"[^"]*"/, `$1"${APP_NAME}"`);
  if (replaced === source) fail("name フィールドが見つかりませんでした。");
  writeFileSync(path, replaced, "utf8");
  console.log(`package.json の name を ${current} から ${APP_NAME} へ変更しました。`);
}

/** 配布物とウィンドウに出るアプリ名を差し替える。 */
function applyProductName() {
  const path = join(editorDir, "build", "electronBuilderConfig.ts");
  if (!existsSync(path)) {
    console.log("electronBuilderConfig.ts が無いため productName の変更は省略しました。");
    return;
  }

  const source = readFileSync(path, "utf8");
  if (source.includes(`productName: "${PRODUCT_NAME}"`)) {
    console.log(`productName は既に ${PRODUCT_NAME} です。`);
    return;
  }

  const replaced = source.replace(/productName:\s*"[^"]*"/, `productName: "${PRODUCT_NAME}"`);
  if (replaced === source) fail("productName が見つかりませんでした。");
  writeFileSync(path, replaced, "utf8");
  console.log(`productName を ${PRODUCT_NAME} へ変更しました。`);
}

/** 和風テーマを追加する。テーマ定義は別ファイルへ置き、登録の 1 行だけを足す。 */
function applyTheme() {
  const themeDir = join(editorDir, "src", "domain", "theme");
  const indexPath = join(themeDir, "index.ts");
  if (!existsSync(indexPath)) {
    console.log("theme/index.ts が無いためテーマの追加は省略しました。");
    return;
  }

  copyFileSync(join(toolsDir, "irodori-theme.ts"), join(themeDir, "irodori.ts"));

  const source = readFileSync(indexPath, "utf8");
  if (source.includes("irodoriThemes")) {
    console.log("和風テーマは既に登録されています。");
    return;
  }

  const withImport = source.startsWith("import")
    ? source.replace(/^(import[^\n]*\n)/, `$1${THEME_IMPORT}\n`)
    : `${THEME_IMPORT}\n${source}`;

  const replaced = withImport.replace(
    /export const themes = \[([^\]]*)\];/,
    (_match, current) => `export const themes = [${current.trim()}, ...irodoriThemes];`,
  );
  if (replaced === withImport) fail("themes の配列が見つかりませんでした。");

  writeFileSync(indexPath, replaced, "utf8");
  console.log("和風テーマ（彩 / 墨）を追加しました。");
}

/** タイトルバーのアイコンを差し替える。配布した exe のアイコンにもなる。 */
function applyIcon() {
  const source = join(toolsDir, "irodori-icon.png");
  const target = join(editorDir, "public", "icon.png");
  if (!existsSync(source)) {
    console.log("irodori-icon.png が無いためアイコンの差し替えは省略しました。");
    return;
  }
  if (!existsSync(dirname(target))) {
    console.log("public/ が無いためアイコンの差し替えは省略しました。");
    return;
  }
  copyFileSync(source, target);
  console.log("アイコンを差し替えました（public/icon.png）。");
}

/** 表示名を差し替える。判定は置換後の文字列で行う（置換前を含んだままになる形もあるため）。 */
function applyTitle() {
  for (const target of titleTargets) {
    const path = join(editorDir, ...target.file);
    if (!existsSync(path)) {
      console.log(`${target.label}: 対象のファイルが無いため省略しました。`);
      continue;
    }

    const source = readFileSync(path, "utf8");
    // 削除（patched が空）の場合は、original が消えていれば適用済みとみなす。
    const applied =
      target.patched === "" ? !source.includes(target.original) : source.includes(target.patched);
    if (applied) {
      console.log(`${target.label}: 適用済みです。`);
      continue;
    }
    if (!source.includes(target.original)) {
      console.log(`${target.label}: 対象の記述が見つかりませんでした。上流の更新で変わった可能性があります。`);
      continue;
    }

    writeFileSync(path, source.replace(target.original, target.patched), "utf8");
    console.log(
      target.patched === ""
        ? `${target.label}: 取り除きました。`
        : `${target.label}: ${TITLE_NAME} へ変更しました。`,
    );
  }
}

applyPackageName();
applyProductName();
applyTheme();
applyIcon();
applyTitle();

console.log("\n設定画面のテーマから「彩（あかるい）」「墨（くらい）」を選べます。");
