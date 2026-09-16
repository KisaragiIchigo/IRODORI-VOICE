/**
 * VOICEVOX エディタへ IRODORI-VOICE 用の手を入れる。
 *
 * 当てるのは次の 9 つ。いずれも上流の該当箇所が変わっていた場合は何もせずに終了する
 * （当てずっぽうに置換して壊さないため）。
 *
 *   1. 長文警告の閾値
 *      エディタは 80 文字を超えた行へ「文章が長いと正常に動作しない可能性があります」
 *      と表示する。本家エンジンが長文で不安定になる前提の注意書きで、IRODORI-VOICE には
 *      当てはまらない（受け取った文を内部で区間へ割ってから合成する）。300 文字へ上げる。
 *
 *   2. 既定テーマを「墨（くらい）」にする
 *      テーマを足しただけでは選ばれない。設定の初期値そのものを差し替える。
 *      一度でも起動した環境では保存済みの設定が優先されるため、その場合は
 *      設定→テーマから選び直す必要がある。
 *
 *   3. 「音声モデルの管理」画面をエディタ内へ組み込む
 *      音声モデルの取り込み・作成、話者の作成を行う画面をエンジンが配信している。
 *      これをエディタ内のダイアログとして開けるようにし、メニューへ入口を置く。
 *      別のブラウザや別のバッチへ動線が分かれると、どこで何をするのか分からなくなる。
 *
 *   4. 貼り付けたテキストの分割で鉤括弧の中を守る
 *      本家は「。」の後ろへ一律で改行を入れるため、鉤括弧で囲まれたセリフが途中で切れる。
 *      切れた断片を単体で合成すると高域が落ちてこもった音になるため、囲みの外の句点
 *      だけで割るようにする。
 *
 *   5. 歌唱に対応した話者がいない構成でソングエディタを扱わない
 *      このエンジンは歌唱合成に対応せず、/singers も空を返す。本家のソングエディタは
 *      歌手が 1 人もいない状態を想定しておらず、既定の歌手を決める箇所で配列の先頭を
 *      無条件に読むため TypeError で落ちる。しかもこれを呼ぶのは新規プロジェクトの
 *      作成で、トーク側しか使っていなくても巻き添えになる。歌手がいなければ歌手を
 *      設定せずに抜けるようにし、併せてソングへの切り替えボタンを出さない。
 *
 *   6. 更新確認の失敗を握る
 *      useFetchNewUpdateInfos は取得処理を catch の無い即時実行関数へ投げっぱなしにしている。
 *      IRODORI-VOICE は取得先を .env でエンジン自身（update_infos.json）にしているため、
 *      エンジンが起動しきる前に走るこの確認は必ず失敗する。しかもヘルプと更新通知の
 *      2 か所から呼ばれるので、起動のたびに未処理の rejection が 2 件出て、
 *      ErrorBoundary が「Failed to fetch」として記録していた。更新なしとして扱う。
 *
 *   7. ヘルプの文面を IRODORI-VOICE のものへ差し替える
 *      public/ に置かれた利用規約・使い方・Q&A・お問い合わせ・開発コミュニティは
 *      VOICEVOX のもので、利用規約とプライバシーポリシーに至っては本家リポジトリでは
 *      ダミー文（本家の配布物では CI が本物へ差し替える）。そのままではヘルプに
 *      「ダミー利用規約」と表示される。IRODORI-VOICE 向けに書いたものへ入れ替える。
 *
 *   8. 配布ビルドの形式とアプリ ID
 *      本家の Windows 向けターゲットは nsis-web で、インストーラが本体を分割ダウンロード
 *      する形式。配布サーバーが前提のため手元のビルドでは使えず、付属の installer.nsh も
 *      952 行すべてがその前提で書かれている。インストーラ（nsis）・単一実行ファイル
 *      （portable）・フォルダそのまま（dir）の 3 つを出す形へ変え、nsis と portable の
 *      設定を新たに置く。あわせて appId が VOICEVOX 公式と同一だと、インストール情報が
 *      混ざるため分ける。著作権表示にはエディタ本体の権利者を残す。
 *
 *   9. 読み方＆アクセント辞書をファイルで持ち運べるようにする
 *      本家の辞書画面には書き出しも取り込みも無く、登録した語はそのエンジンの中だけに
 *      溜まっていく。AivisSpeech が書き出すファイルと同じ形で読み書きできるようにして、
 *      両方のソフトで同じ語を使えるようにする。形を合わせる仕事はエンジンが受け持ち、
 *      エディタ側はファイルの選択と受け渡しだけを行う。
 *
 * 追加するファイルは tools/editor-patch/ に置いてある。パッチ適用時にコピーし、
 * --revert で削除する。本家にもとから在るファイルの差し替えは overrides で行い、
 * こちらは初回に <ファイル名>.orig を残して --revert で書き戻す。
 *
 * 使い方:
 *   node tools/patch-editor.mjs            適用する
 *   node tools/patch-editor.mjs --revert   本家の状態へ戻す
 */

import { copyFileSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const toolsDir = dirname(fileURLToPath(import.meta.url));
const root = dirname(toolsDir);
const revert = process.argv.includes("--revert");

const editorRoot = join(root, "editor-voicevox");
const editorSrc = join(editorRoot, "src");
const assetDir = join(toolsDir, "editor-patch");
const editorPublic = join(editorRoot, "public");

/** 追加するファイル。tools/editor-patch/ からエディタへコピーする。 */
const additions = [
  {
    from: join(assetDir, "AdminDialog.vue"),
    to: join(editorSrc, "components", "Dialog", "AdminDialog.vue"),
  },
  {
    from: join(assetDir, "adminDialogState.ts"),
    to: join(editorSrc, "components", "Dialog", "adminDialogState.ts"),
  },
  {
    from: join(assetDir, "irodoriTextSplit.ts"),
    to: join(editorSrc, "domain", "irodoriTextSplit.ts"),
  },
  {
    from: join(assetDir, "aivisDictFile.ts"),
    to: join(editorSrc, "domain", "aivisDictFile.ts"),
  },
  {
    from: join(assetDir, "irodoriTextSplit.spec.ts"),
    to: join(editorRoot, "tests", "unit", "domain", "irodoriTextSplit.spec.ts"),
  },
  {
    from: join(assetDir, "build", "irodori-installer.nsh"),
    to: join(editorRoot, "build", "irodori-installer.nsh"),
  },
];

/**
 * 本家にもとから在るファイルを丸ごと差し替える。
 *
 * additions と違い元のファイルが存在するため、--revert のために初回だけ <名前>.orig を
 * 残す。additions と同じ扱い（revert で削除）にすると、本家のファイルまで消えてしまう。
 */
const overrides = [
  { from: join(assetDir, "help", "policy.md"), to: join(editorPublic, "policy.md") },
  { from: join(assetDir, "help", "privacyPolicy.md"), to: join(editorPublic, "privacyPolicy.md") },
  { from: join(assetDir, "help", "howtouse.md"), to: join(editorPublic, "howtouse.md") },
  { from: join(assetDir, "help", "qAndA.md"), to: join(editorPublic, "qAndA.md") },
  { from: join(assetDir, "help", "contact.md"), to: join(editorPublic, "contact.md") },
  {
    from: join(assetDir, "help", "ossCommunityInfos.md"),
    to: join(editorPublic, "ossCommunityInfos.md"),
  },
  { from: join(assetDir, "help", "updateInfos.json"), to: join(editorPublic, "updateInfos.json") },
];

/** 既存ファイルへの置換。 */
const patches = [
  {
    name: "長文警告の閾値",
    file: join(editorSrc, "components", "Talk", "AudioCell.vue"),
    original: "audioTextBuffer.length >= 80",
    patched: "audioTextBuffer.length >= 300",
  },
  {
    name: "分割処理の読み込み",
    file: join(editorSrc, "components", "Talk", "AudioCell.vue"),
    original: "import { getDefaultStyle } from \"@/domain/talk\";",
    patched:
      "import { getDefaultStyle } from \"@/domain/talk\";\n" +
      "import { splitTextByPeriodAndNewLine } from \"@/domain/irodoriTextSplit\";",
  },
  {
    name: "貼り付け時の分割",
    file: join(editorSrc, "components", "Talk", "AudioCell.vue"),
    original:
      "      PERIOD_AND_NEW_LINE: (text) =>\n" +
      "        text.replaceAll(\"。\", \"。\\r\\n\").split(/[\\r\\n]/),",
    patched: "      PERIOD_AND_NEW_LINE: splitTextByPeriodAndNewLine,",
  },
  {
    name: "ｲﾝﾄﾈｰｼｮﾝ欄・長さ欄のタブ",
    file: join(editorSrc, "components", "Talk", "AudioDetail.vue"),
    original: `            <QTab name="accent" label="ｱｸｾﾝﾄ" />
            <QTab
              name="pitch"
              label="ｲﾝﾄﾈｰｼｮﾝ"
              :disable="
                !(supportedFeatures && supportedFeatures.adjustMoraPitch)
              "
            />
            <QTab
              name="length"
              label="長さ"
              :disable="
                !(supportedFeatures && supportedFeatures.adjustPhonemeLength)
              "
            />
`,
    patched: `            <!-- ｲﾝﾄﾈｰｼｮﾝ欄と長さ欄は使わないため、タブを出さない。 -->
            <QTab name="accent" label="ｱｸｾﾝﾄ" />
`,
  },
  {
    name: "ｲﾝﾄﾈｰｼｮﾝ欄・長さ欄の切り替えホットキー",
    file: join(editorSrc, "components", "Talk", "AudioDetail.vue"),
    original: `registerHotkeyWithCleanup({
  editor: "talk",
  name: "ｲﾝﾄﾈｰｼｮﾝ欄を表示",
  callback: () => {
    if (supportedFeatures.value?.adjustMoraPitch) {
      selectedDetail.value = "pitch";
    }
  },
});
registerHotkeyWithCleanup({
  editor: "talk",
  name: "長さ欄を表示",
  callback: () => {
    if (supportedFeatures.value?.adjustPhonemeLength) {
      selectedDetail.value = "length";
    }
  },
});
registerHotkeyWithCleanup({
  editor: "talk",
  name: "全体のイントネーションをリセット",`,
    patched: `// タブを出していない欄へ 2 / 3 キーで移動しないよう、登録そのものを行わない。
registerHotkeyWithCleanup({
  editor: "talk",
  name: "全体のイントネーションをリセット",`,
  },
  {
    name: "テキスト自動分割の説明",
    file: join(editorSrc, "components", "Dialog", "SettingDialog", "SettingDialog.vue"),
    original: "description: '句点と改行を基にテキストを分割します。',",
    // 1 行に収まらなくなるため、prettier の整形結果と同じ折り返しで置き換える。
    patched:
      "description:\n" +
      "                        '句点と改行を基にテキストを分割します。鉤括弧の中の句点では分割しません。',",
  },
  {
    name: "ダイアログの組み込み",
    file: join(editorSrc, "components", "Dialog", "AllDialog.vue"),
    original: "  <HelpDialog v-model:dialogOpened=\"isHelpDialogOpenComputed\" />\n</template>",
    patched:
      "  <HelpDialog v-model:dialogOpened=\"isHelpDialogOpenComputed\" />\n" +
      "  <AdminDialog />\n</template>",
  },
  {
    name: "ダイアログの読み込み",
    file: join(editorSrc, "components", "Dialog", "AllDialog.vue"),
    original: "import HelpDialog from \"@/components/Dialog/HelpDialog/HelpDialog.vue\";",
    patched:
      "import HelpDialog from \"@/components/Dialog/HelpDialog/HelpDialog.vue\";\n" +
      "import AdminDialog from \"@/components/Dialog/AdminDialog.vue\";",
  },
  {
    name: "エンジンメニューへの項目追加",
    file: join(editorSrc, "backend", "electron", "renderer", "menuBarData.ts"),
    original:
      "    const allEnginesSubMenuData = removeNullableAndBoolean<MenuItemData>([\n      enableMultiEngine.value && {",
    patched:
      "    const allEnginesSubMenuData = removeNullableAndBoolean<MenuItemData>([\n" +
      "      {\n" +
      "        type: \"button\",\n" +
      "        label: \"音声モデルの管理\",\n" +
      "        onClick: () => {\n" +
      "          isAdminDialogOpen.value = true;\n" +
      "        },\n" +
      "        disableWhenUiLocked: false,\n" +
      "      },\n" +
      "      enableMultiEngine.value && {",
  },
  {
    name: "メニュー側の読み込み",
    file: join(editorSrc, "backend", "electron", "renderer", "menuBarData.ts"),
    original: "import { removeNullableAndBoolean } from \"@/helpers/arrayHelper\";",
    patched:
      "import { removeNullableAndBoolean } from \"@/helpers/arrayHelper\";\n" +
      "import { isAdminDialogOpen } from \"@/components/Dialog/adminDialogState\";",
  },
  {
    name: "既定テーマ（ストアの初期値）",
    file: join(editorSrc, "store", "setting.ts"),
    original: '  currentTheme: "Default",',
    patched: '  currentTheme: "IrodoriDark",',
  },
  {
    name: "既定テーマ（設定ファイルの既定値）",
    file: join(editorSrc, "type", "preload.ts"),
    original: '    currentTheme: z.string().default("Default"),',
    patched: '    currentTheme: z.string().default("IrodoriDark"),',
  },
  {
    name: "歌手不在時の既定歌手の決定",
    file: join(editorSrc, "store", "singing.ts"),
    original: `      const defaultStyleId =
        userOrderedCharacterInfos[0].metas.styles[0].styleId;
      const styleId = singer?.styleId ?? defaultStyleId;
`,
    patched: `      // 歌唱に対応したスタイルを持つエンジンが 1 つも無い構成では、既定の歌手を決められない。
      // ここで [0] を読むと TypeError になり、これを呼ぶ新規プロジェクトの作成ごと巻き添えで失敗する。
      const defaultStyleId =
        userOrderedCharacterInfos[0]?.metas.styles[0]?.styleId;
      const styleId = singer?.styleId ?? defaultStyleId;
      if (styleId == undefined) {
        logger.warn("歌唱に対応したスタイルがないため、歌手を設定しません。");
        return;
      }
`,
  },
  {
    name: "ソング切り替えの表示条件",
    file: join(editorSrc, "components", "Menu", "MenuBar", "TitleBarEditorSwitcher.vue"),
    original: `  <QBtnToggle
    :modelValue="openedEditor"`,
    patched: `  <QBtnToggle
    v-if="isSongEditorAvailable"
    :modelValue="openedEditor"`,
  },
  {
    name: "ソング切り替えの判定",
    file: join(editorSrc, "components", "Menu", "MenuBar", "TitleBarEditorSwitcher.vue"),
    original: `const uiLocked = computed(() => store.getters.UI_LOCKED);
`,
    patched: `const uiLocked = computed(() => store.getters.UI_LOCKED);

// 歌唱に対応したスタイルを持つエンジンが無いときは、ソングエディタを開いても歌手を選べない。
// 切り替える先が無いので、トーク 1 択として切り替えボタン自体を出さない。
const isSongEditorAvailable = computed(
  () => store.getters.GET_ALL_VOICES("singerLike").length > 0,
);
`,
  },
  {
    name: "ソングを開いたまま終了した場合の復帰",
    file: join(editorSrc, "components", "App.vue"),
    original: `  // 辞書を同期
  await store.actions.SYNC_ALL_USER_DICT();
`,
    patched: `  // 辞書を同期
  await store.actions.SYNC_ALL_USER_DICT();

  // 歌唱に対応したスタイルを持つエンジンが無い場合、ソングエディタでは歌手を選べない。
  // 前回ソングを開いたまま終了していると切り替えボタンが出ず戻れなくなるため、トークへ戻す。
  if (
    store.state.openedEditor === "song" &&
    store.getters.GET_ALL_VOICES("singerLike").length === 0
  ) {
    await store.actions.SET_ROOT_MISC_SETTING({
      key: "openedEditor",
      value: "talk",
    });
  }
`,
  },
  {
    name: "更新確認のログ出力",
    file: join(editorSrc, "composables", "useFetchNewUpdateInfos.ts"),
    original: `import { z } from "zod";
`,
    patched: `import { z } from "zod";
import { createLogger } from "@/helpers/log";
`,
  },
  {
    name: "更新確認のロガー",
    file: join(editorSrc, "composables", "useFetchNewUpdateInfos.ts"),
    original: `} from "@/type/preload";
`,
    patched: `} from "@/type/preload";

const logger = createLogger("useFetchNewUpdateInfos");
`,
  },
  {
    name: "更新確認の失敗を握る",
    file: join(editorSrc, "composables", "useFetchNewUpdateInfos.ts"),
    original: `  })();

  return result;
`,
    patched: `  })().catch((error: unknown) => {
    // 取得できなくてもエディタの動作には影響しないため、更新なしとして扱う。
    // IRODORI-VOICE は取得先をエンジン自身にしているので、エンジンが起動しきる前に走る
    // この確認は必ず失敗する。放っておくと未処理の rejection になり、ErrorBoundary が
    // 起動のたびに「Failed to fetch」を記録する。
    logger.warn("更新情報を取得できませんでした。", error);
    result.value = { status: "updateNotAvailable" };
  });

  return result;
`,
  },
  {
    name: "話者追加時の並び替え画面",
    file: join(editorSrc, "store", "engine.ts"),
    original: `      if (mergedResult.anyNewCharacters) {
        void actions.SET_DIALOG_OPEN({
          isOldCharacterOrderDialogOpen: true,
        });
      }
`,
    patched: `      // 本家は未登録の話者を見つけると並び替え画面を全画面で開く。キャラクターが
      // 増えるのが年に数回という前提の作りだが、IRODORI-VOICE では管理画面から
      // 話者をいくつでも作れるため、作るたびに開いて邪魔になる。
      // 並び替えは「設定」→「キャラクター並び替え・試聴」からいつでも開けるので、
      // 自動で開くのをやめる。
`,
  },
  {
    name: "ビルド出力先の差し替え口",
    file: join(editorRoot, "build", "electronBuilderConfig.ts"),
    original: `  directories: {
    output: "dist_electron",
    buildResources: "build",
  },`,
    patched: `  directories: {
    // NSIS のコンパイラ（makensis）は、渡されたパスを ANSI として扱うため非 ASCII の
    // パスを開けない。プロジェクトの置き場所に日本語が含まれていると、生成した
    // アイコン（.icon-ico/icon.ico）の読み込みに失敗してインストーラを作れない。
    // 出力先だけを ASCII のパスへ逃がせるようにしておく（コンパイル.bat が指定する）。
    output: process.env.IRODORI_BUILD_OUTPUT ?? "dist_electron",
    buildResources: "build",
  },`,
  },
  {
    name: "配布ビルドの形式",
    file: join(editorRoot, "build", "electronBuilderConfig.ts"),
    original: `    target: [
      {
        target: "nsis-web",
        arch: ["x64"],
      },
    ],`,
    patched: `    // 既定はインストーラ・単一実行ファイル・フォルダの 3 形式。
    // IRODORI_BUILD_TARGETS で絞れるようにしているのは、GPU 版のためです。
    // NSIS は 32bit 実装で、埋め込むアプリが 2GB 前後を超えると
    // extractEmbeddedAppPackage で失敗します。CUDA ランタイムを含む GPU 版は
    // 5GB あるため nsis と portable を作れません（実測で確認済み）。
    // その構成では dir だけを指定します。
    target: (process.env.IRODORI_BUILD_TARGETS ?? "nsis,portable,dir")
      .split(",")
      .map((name) => ({ target: name.trim(), arch: ["x64"] })),`,
  },
  {
    name: "インストーラと単一実行ファイルの設定",
    file: join(editorRoot, "build", "electronBuilderConfig.ts"),
    original: `  nsisWeb: {`,
    patched: `  nsis: {
    // 本家の build/installer.nsh は本体を分割ダウンロードする前提で 952 行すべてが
    // 書かれている。electron-builder は buildResources 直下の installer.nsh を
    // include 未指定なら自動で読むため、明示的に空のスクリプトを指すことで止める。
    // 指定しないと nsis-web でしか定義されない変数を参照して makensis が警告を出し、
    // 警告がエラー扱いのためビルドが落ちる。
    include: "build/irodori-installer.nsh",
    oneClick: false,
    allowToChangeInstallationDirectory: true,
    artifactName: "\${productName} Setup.\${ext}",
    // 話者・設定・辞書は %APPDATA%/IRODORI-VOICE にある。アンインストールで消さない。
    deleteAppDataOnUninstall: false,
  },
  portable: {
    artifactName: "\${productName} Portable.\${ext}",
    // 展開先を固定する。既定では起動のたびに別のテンポラリへ 1.5GB を展開するため、
    // 2 回目以降が速くならない。
    unpackDirName: "irodori-voice",
  },
  nsisWeb: {`,
  },
  {
    name: "辞書の書き出しと取り込み（ボタン）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `            <QSpace />
            <!-- close button -->`,
    patched: `            <QSpace />
            <!-- AivisSpeech と同じ形のファイルで辞書を持ち運ぶ。 -->
            <QBtn
              flat
              dense
              noCaps
              icon="file_download"
              label="書き出し"
              color="display"
              aria-label="辞書をファイルへ書き出す"
              :disable="uiLocked"
              @click="exportDict"
            />
            <QBtn
              flat
              dense
              noCaps
              icon="file_upload"
              label="取り込み"
              color="display"
              aria-label="辞書をファイルから取り込む"
              :disable="uiLocked"
              @click="importDict"
            />
            <!-- close button -->`,
  },
  {
    name: "辞書の書き出しと取り込み（読み込み）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `import { UnreachableError } from "@/type/utility";`,
    patched: `import { UnreachableError } from "@/type/utility";
import {
  defaultAivisDictFileName,
  describeImportSummary,
  fetchAivisDictFile,
  readAivisDictFile,
  sendAivisDictFile,
} from "@/domain/aivisDictFile";
import { getValueOrThrow } from "@/type/result";`,
  },
  {
    name: "辞書の書き出しと取り込み（処理）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `const closeDialog = () => {`,
    patched: `/** 辞書のやり取りに使うエンジン。1 つ目のエンジンが辞書の持ち主になる。 */
const dictEngine = () => store.getters.GET_SORTED_ENGINE_INFOS[0];

const alertDict = (title: string, message: string) => {
  void store.actions.SHOW_ALERT_DIALOG({ title, message });
};

const runExportDict = async () => {
  const engine = dictEngine();
  if (!engine) {
    alertDict("辞書を書き出せませんでした", "エンジンに接続できていません。");
    return;
  }
  // 語が無いまま書き出すと、読み込み側が受け取れないファイルができる。
  if (Object.keys(userDict.value).length === 0) {
    alertDict(
      "辞書を書き出せませんでした",
      "辞書にはまだ単語が 1 つも登録されていません。",
    );
    return;
  }

  const filePath = await window.backend.showSaveFileDialog({
    title: "辞書を書き出す",
    name: "辞書ファイル",
    extensions: ["json"],
    defaultPath: defaultAivisDictFileName(new Date()),
  });
  if (!filePath) return;

  try {
    const contents = await lockUiWhile(fetchAivisDictFile(engine));
    await window.backend
      .writeFile({ filePath, buffer: new TextEncoder().encode(contents) })
      .then(getValueOrThrow);
  } catch (e) {
    alertDict(
      "辞書を書き出せませんでした",
      e instanceof Error ? e.message : "書き出しの途中で失敗しました。",
    );
    window.backend.logError(e);
    return;
  }

  alertDict(
    "辞書を書き出しました",
    \`\${filePath} へ保存しました。AivisSpeech でもそのまま読み込めます。\`,
  );
};

const runImportDict = async () => {
  const engine = dictEngine();
  if (!engine) {
    alertDict("辞書を取り込めませんでした", "エンジンに接続できていません。");
    return;
  }

  const filePath = await window.backend.showOpenFileDialog({
    title: "辞書を取り込む",
    name: "辞書ファイル",
    mimeType: "application/json",
    extensions: ["json"],
  });
  if (!filePath) return;

  let summary;
  try {
    const bytes = await window.backend
      .readFile({ filePath })
      .then(getValueOrThrow);
    summary = await lockUiWhile(
      sendAivisDictFile(engine, readAivisDictFile(bytes)),
    );
  } catch (e) {
    alertDict(
      "辞書を取り込めませんでした",
      e instanceof Error ? e.message : "取り込みの途中で失敗しました。",
    );
    window.backend.logError(e);
    return;
  }

  // 取り込んだ語を一覧へ出し、他のエンジンへも行き渡らせる。編集していた語は
  // 上書きされている可能性があるため、選択を外してから読み直す。
  currentWord.value = null;
  await loadUserDict();
  alertDict("辞書を取り込みました", describeImportSummary(summary));
};

// 編集中の語があれば先に片付ける。書き出しでは保存前の変更が抜け落ちないように、
// 取り込みでは取り込んだ語を保存前の内容で上書きしないようにするため。
const exportDict = () => {
  void beforeMove(() => {
    void runExportDict();
  });
};
const importDict = () => {
  void beforeMove(() => {
    void runImportDict();
  });
};

const closeDialog = () => {`,
  },
  {
    name: "アプリ ID と著作権表示",
    file: join(editorRoot, "build", "electronBuilderConfig.ts"),
    original: `  appId: "jp.hiroshiba.voicevox",
  copyright: "Hiroshiba Kazuyuki",`,
    patched: `  appId: "jp.irodori-voice.app",
  copyright: "Hiroshiba Kazuyuki (VOICEVOX Editor) / IRODORI-VOICE",`,
  },
];

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
