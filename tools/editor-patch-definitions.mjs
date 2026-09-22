/**
 * エディタへ当てる内容の宣言。
 *
 * 当てるのは次の 16 個。いずれも上流の該当箇所が変わっていた場合は何もせずに終了する
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
 *  10. フレーズ分割辞書をエディタから登録できるようにする
 *      長い複合語をひと塊のまま渡すとモデルが読みを外すため、どこで区切るかを表記の
 *      側で伝える辞書をエンジンが持っている。これまで登録の口は API だけで画面が無く、
 *      利用者はファイルを手で開くしかなかった。読み方＆アクセント辞書と同じ形の画面を
 *      足し、メニューへ入口を置く。辞書そのものの扱いはエンジンが持ち、エディタ側は
 *      一覧の表示と受け渡しだけを行う。
 *
 *  11. 合成へ現在の本文を渡す
 *      本文編集時に残る古い kana ではなく、送信時にメモ・ルビを処理した本文を使う。
 *      IRODORI-VOICE のエンジン ID に限定し、他のエンジンのかな表記は変更しない。
 *
 *  12. 辞書の一覧を検索で絞り込む
 *      語が増えると一覧を目で追えなくなる。読み方＆アクセント辞書とフレーズ分割辞書の
 *      両方の一覧へ検索欄を置く。照合は単語と読み（分割辞書では単語と分割後の文字列）の
 *      両方に当て、全角と半角・大小文字・ひらがなとカタカナの違いを吸収する。正規表現へ
 *      切り替えることもでき、書き損じは一覧を消さずに理由だけを出す。判定は
 *      domain/dictSearch.ts が持つ。
 *
 *  13. 読み方の登録をフレーズ分割辞書へ同時登録する
 *      エンジンは辞書の読みを語の切れ目に限って当てるため、解析が 1 語として切る複合語の
 *      内側にある登録語は当たらない。これまでは利用者がフレーズ分割辞書へ同じ語を手で
 *      書き足す必要があった。単語エディタへ「フレーズ分割辞書にも登録する」を置き、
 *      ``単語=_単語_`` の形（ポーズを空けずに語の前後を区切る形）で分割辞書へも通す。
 *      足し引きの計画は domain/dictSplitLink.ts が持ち、手で直した分割は上書きしない。
 *
 *  14. 書き出しの通知から保存先を開けるようにする
 *      本家は書き出し成功の通知へ「今後このメッセージを表示しない」だけを置く。書き出した
 *      ファイルの置き場所へは、通知を閉じてから自分でたどり直すしかない。動画へ差し込む
 *      までが一続きの作業なので、通知からそのまま保存先を開けるようにする。ボタンを
 *      「保存されたフォルダを開く」へ差し替え、開く手段のある Electron 版でのみ出す。
 *
 *  15. 新しい話者を並び順と既定スタイルへ自動で登録する
 *      本家は未登録の話者を見つけると並び替え画面を全画面で開き、そこで並び順が決まる。
 *      IRODORI-VOICE は管理画面から話者をいくつでも作れるため、その画面を自動では
 *      出さない。ただし並び順に無い話者は一覧の先頭へ回って既定の話者になり、既定
 *      スタイルが無いままだと新しい行を作るたびに落ちる（テキスト欄の追加も、複数行の
 *      貼り付けも通らなくなる）。画面を出す代わりに、増えた話者を並び順の末尾へ足して
 *      既定スタイルを埋める REGISTER_NEW_CHARACTERS を置き、エンジン起動後と
 *      管理画面を閉じたときの両方から呼ぶ。
 *
 *  16. 辞書を書き換えたら、合成済みの音声とクエリを作り直す
 *      合成キャッシュの鍵は本文・クエリ・話者から作るため、辞書を書き換えても鍵が
 *      変わらない。捨てないと、登録したのに前の読みで作った音がそのまま再生される。
 *      クエリも作り直す。エンジンは送られたアクセント句から本文を組み直すため、古い
 *      クエリを送ると読みが辞書を当てる前へ戻り、画面下のカタカナも古いままになる。
 *      単語の追加・変更・削除とフレーズ分割辞書の保存から通す。
 *
 * 追加するファイルは tools/editor-patch/ に置いてある。パッチ適用時にコピーし、
 * --revert で削除する。本家にもとから在るファイルの差し替えは overrides で行い、
 * こちらは初回に <ファイル名>.orig を残して --revert で書き戻す。
 *
 * 当てる手順は patch-editor.mjs が持つ。ここは「どこへ何を」だけを並べる。
 */

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const toolsDir = dirname(fileURLToPath(import.meta.url));

export const root = dirname(toolsDir);
export const editorRoot = join(root, "editor-voicevox");
export const editorSrc = join(editorRoot, "src");
export const editorPublic = join(editorRoot, "public");
export const assetDir = join(toolsDir, "editor-patch");

/** 追加するファイル。tools/editor-patch/ からエディタへコピーする。 */
export const additions = [
  {
    from: join(assetDir, "irodoriExpression.spec.ts"),
    to: join(editorRoot, "tests", "unit", "store", "irodoriExpression.spec.ts"),
  },
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
    from: join(assetDir, "WordSplitManageDialog.vue"),
    to: join(editorSrc, "components", "Dialog", "WordSplitManageDialog.vue"),
  },
  {
    from: join(assetDir, "wordSplits.ts"),
    to: join(editorSrc, "domain", "wordSplits.ts"),
  },
  {
    from: join(assetDir, "dictSearch.ts"),
    to: join(editorSrc, "domain", "dictSearch.ts"),
  },
  {
    from: join(assetDir, "dictSplitLink.ts"),
    to: join(editorSrc, "domain", "dictSplitLink.ts"),
  },
  {
    from: join(assetDir, "irodoriTextSplit.spec.ts"),
    to: join(editorRoot, "tests", "unit", "domain", "irodoriTextSplit.spec.ts"),
  },
  {
    from: join(assetDir, "dictSearch.spec.ts"),
    to: join(editorRoot, "tests", "unit", "domain", "dictSearch.spec.ts"),
  },
  {
    from: join(assetDir, "dictSplitLink.spec.ts"),
    to: join(editorRoot, "tests", "unit", "domain", "dictSplitLink.spec.ts"),
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
export const overrides = [
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
export const patches = [
  {
    name: "保存設定のステレオ既定値",
    file: join(editorSrc, "type", "preload.ts"),
    original: "outputStereo: z.boolean().default(false)",
    patched: "outputStereo: z.boolean().default(true)",
  },
  {
    name: "保存状態のステレオ初期値",
    file: join(editorSrc, "store", "setting.ts"),
    original: "outputStereo: false,",
    patched: "outputStereo: true,",
  },
  {
    name: "合成時に現在の本文の表現指定を渡すための読み抽出",
    file: join(editorSrc, "store", "audioGenerate.ts"),
    original: 'import { generateTempUniqueId } from "./utility";',
    patched: 'import { extractYomiText, generateTempUniqueId } from "./utility";',
  },
  {
    name: "IRODORI-VOICE の合成へ現在の本文を渡す",
    file: join(editorSrc, "store", "audioGenerate.ts"),
    original: `  const audioQuery = audioItem.query;
  if (audioQuery != undefined) {
    audioQuery.outputSamplingRate =`,
    patched: `  const audioQuery = audioItem.query;
  if (audioQuery != undefined) {
    // 本文の編集では query.kana が更新されないため、送信時に表現指定を同期する。
    if (audioItem.voice.engineId === "0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40") {
      audioQuery.kana = extractYomiText(audioItem.text, {
        enableMemoNotation: state.enableMemoNotation,
        enableRubyNotation: state.enableRubyNotation,
      });
    }
    audioQuery.outputSamplingRate =`,
  },
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
    patched: `      // 本家は未登録の話者を見つけると並び替え画面を全画面で開き、そこで並び順を
      // 決めさせる。キャラクターが増えるのが年に数回という前提の作りだが、
      // IRODORI-VOICE では管理画面から話者をいくつでも作れるため、作るたびに開いて
      // 邪魔になる。画面を出す代わりに、増えた話者を並び順の末尾へ黙って足す。
      // 並び替えは「設定」→「キャラクター並び替え・試聴」からいつでも開ける。
      await actions.REGISTER_NEW_CHARACTERS();
`,
  },
  {
    name: "新しい話者の登録",
    file: join(editorSrc, "store", "index.ts"),
    original: `      const newSpeakerUuid = allSpeakerUuid.filter(
        (speakerUuid) => !state.userCharacterOrder.includes(speakerUuid),
      );
      return newSpeakerUuid;
    },
  },
`,
    patched: `      const newSpeakerUuid = allSpeakerUuid.filter(
        (speakerUuid) => !state.userCharacterOrder.includes(speakerUuid),
      );
      return newSpeakerUuid;
    },
  },

  /**
   * 並び順に無い話者を末尾へ足し、既定スタイルを埋める。
   *
   * 本家は新しい話者を見つけると並び替え画面を開き、そこで並び順が決まる。
   * IRODORI-VOICE はその画面を自動で出さないため、代わりにここで登録する。
   * 並び順に無い話者は indexOf が -1 になって一覧の先頭へ回り、既定の話者として
   * 扱われる。そこへ既定スタイルが無いと GENERATE_AUDIO_ITEM が落ち、
   * テキスト欄の追加と複数行の貼り付けができなくなる。
   */
  REGISTER_NEW_CHARACTERS: {
    async action({ state, actions }) {
      const newCharacters = await actions.GET_NEW_CHARACTERS();
      if (newCharacters.length > 0) {
        await actions.SET_USER_CHARACTER_ORDER([
          ...state.userCharacterOrder,
          ...newCharacters,
        ]);
      }
      await actions.LOAD_DEFAULT_STYLE_IDS();
    },
  },
`,
  },
  {
    name: "新しい話者の登録の型",
    file: join(editorSrc, "store", "type.ts"),
    original: `  GET_NEW_CHARACTERS: {
    action(): SpeakerId[];
  };
`,
    patched: `  GET_NEW_CHARACTERS: {
    action(): SpeakerId[];
  };

  REGISTER_NEW_CHARACTERS: {
    action(): Promise<void>;
  };
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
  {
    name: "フレーズ分割辞書ダイアログの読み込み",
    file: join(editorSrc, "components", "Dialog", "AllDialog.vue"),
    original: `import DictionaryManageDialog from "@/components/Dialog/DictionaryManageDialog/DictionaryManageDialog.vue";`,
    patched: `import DictionaryManageDialog from "@/components/Dialog/DictionaryManageDialog/DictionaryManageDialog.vue";
import WordSplitManageDialog from "@/components/Dialog/WordSplitManageDialog.vue";`,
  },
  {
    name: "フレーズ分割辞書ダイアログの組み込み",
    file: join(editorSrc, "components", "Dialog", "AllDialog.vue"),
    original: `  <DictionaryManageDialog
    v-model:dialogOpened="isDictionaryManageDialogOpenComputed"
  />
  <EngineManageDialog`,
    patched: `  <DictionaryManageDialog
    v-model:dialogOpened="isDictionaryManageDialogOpenComputed"
  />
  <WordSplitManageDialog
    v-model:dialogOpened="isWordSplitManageDialogOpenComputed"
  />
  <EngineManageDialog`,
  },
  {
    name: "フレーズ分割辞書ダイアログの開閉状態",
    file: join(editorSrc, "components", "Dialog", "AllDialog.vue"),
    original: `const isAcceptRetrieveTelemetryDialogOpenComputed = computed({`,
    patched: `const isWordSplitManageDialogOpenComputed = computed({
  get: () => store.state.isWordSplitManageDialogOpen,
  set: (val) =>
    store.actions.SET_DIALOG_OPEN({
      isWordSplitManageDialogOpen: val,
    }),
});

const isAcceptRetrieveTelemetryDialogOpenComputed = computed({`,
  },
  {
    name: "設定メニューへフレーズ分割辞書を追加",
    file: join(editorSrc, "components", "Menu", "MenuBar", "useCommonMenuBarData.ts"),
    original: `        {
          type: "button",
          label: "読み方＆アクセント辞書",
          onClick() {
            void store.actions.SET_DIALOG_OPEN({
              isDictionaryManageDialogOpen: true,
            });
          },
          disableWhenUiLocked: true,
        },
`,
    patched: `        {
          type: "button",
          label: "読み方＆アクセント辞書",
          onClick() {
            void store.actions.SET_DIALOG_OPEN({
              isDictionaryManageDialogOpen: true,
            });
          },
          disableWhenUiLocked: true,
        },
        {
          type: "button",
          label: "フレーズ分割辞書",
          onClick() {
            void store.actions.SET_DIALOG_OPEN({
              isWordSplitManageDialogOpen: true,
            });
          },
          disableWhenUiLocked: true,
        },
`,
  },
  {
    name: "フレーズ分割辞書ダイアログの状態の型",
    file: join(editorSrc, "store", "type.ts"),
    original: `  isDictionaryManageDialogOpen: boolean;
`,
    patched: `  isDictionaryManageDialogOpen: boolean;
  isWordSplitManageDialogOpen: boolean;
`,
  },
  {
    name: "フレーズ分割辞書ダイアログの状態の初期値",
    file: join(editorSrc, "store", "ui.ts"),
    original: `  isDictionaryManageDialogOpen: false,
`,
    patched: `  isDictionaryManageDialogOpen: false,
  isWordSplitManageDialogOpen: false,
`,
  },
  {
    name: "辞書の検索と同時登録（読み込み）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `import { getValueOrThrow } from "@/type/result";`,
    patched: `import { getValueOrThrow } from "@/type/result";
import BaseCheckbox from "@/components/Base/BaseCheckbox.vue";
import { createDictMatcher } from "@/domain/dictSearch";
import {
  isSplitRegistered,
  planSplitLink,
  planSplitUnlink,
} from "@/domain/dictSplitLink";
import {
  type WordSplits,
  fetchWordSplits,
  sendWordSplits,
} from "@/domain/wordSplits";`,
  },
  {
    name: "辞書の検索と同時登録（computed の読み込み）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `import { ref, watch } from "vue";`,
    patched: `import { computed, ref, watch } from "vue";`,
  },
  {
    name: "辞書の検索と同時登録（状態）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `const userDict = ref<Record<string, UserDictWord>>({});`,
    patched: `const userDict = ref<Record<string, UserDictWord>>({});

/** フレーズ分割辞書。同時登録の状態を出すために、辞書を読むついでに読んでおく。 */
const wordSplits = ref<WordSplits>({});

const searchQuery = ref("");
const searchUsesRegex = ref(false);

/** 検索の照合器。書き損じた正規表現はここで受け止める。 */
const matcher = computed(() =>
  createDictMatcher(
    searchQuery.value,
    searchUsesRegex.value ? "regex" : "text",
  ),
);

const searchError = computed(() =>
  matcher.value.type === "error" ? matcher.value.message : undefined,
);

/** 一覧に出す単語。単語と読みの両方を照合に使う。 */
const filteredWords = computed<[string, UserDictWord][]>(() => {
  const entries = Object.entries(userDict.value);
  const current = matcher.value;
  // 正規表現が書き損じの間は絞り込まない。入力の途中で一覧が消えると、何を直せば
  // よいのか分からなくなる。理由は検索欄の下に出す。
  if (current.type !== "matcher") return entries;
  return entries.filter(([, word]) =>
    current.matches([word.surface, word.yomi]),
  );
});

const searchCount = computed(() => {
  const total = Object.keys(userDict.value).length;
  const shown = filteredWords.value.length;
  return shown === total ? \`\${total} 件\` : \`\${shown} / \${total} 件\`;
});`,
  },
  {
    name: "辞書の検索と同時登録（検索欄）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `            <div class="list">
              <BaseListItem
                v-for="(value, key) in userDict"`,
    patched: `            <div class="search">
              <BaseTextField
                v-model="searchQuery"
                ariaLabel="単語を検索"
                placeholder="単語・読みで検索"
                :hasError="searchError != undefined"
              >
                <template #error>{{ searchError }}</template>
              </BaseTextField>
              <div class="search-row">
                <BaseCheckbox
                  v-model:checked="searchUsesRegex"
                  label="正規表現"
                />
                <div class="search-count">{{ searchCount }}</div>
              </div>
            </div>
            <div class="list">
              <BaseListItem
                v-for="[key, value] in filteredWords"`,
  },
  {
    name: "辞書の検索と同時登録（一覧が空のとき）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `              </BaseListItem>
            </div>
          </template>`,
    patched: `              </BaseListItem>
              <div v-if="filteredWords.length === 0" class="list-empty">
                {{
                  Object.keys(userDict).length === 0
                    ? "まだ単語が登録されていません。"
                    : "検索に一致する単語がありません。"
                }}
              </div>
            </div>
          </template>`,
  },
  {
    name: "辞書の検索と同時登録（検索欄の見た目）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `.list {
  display: flex;
  flex-direction: column;
  width: 240px;
}`,
    patched: `.search {
  display: flex;
  flex-direction: column;
  gap: vars.$gap-1;
  width: 240px;
  margin-bottom: vars.$padding-1;
}

.search-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: vars.$gap-1;
}

.search-count {
  font-size: 0.75rem;
  color: colors.$display;
  white-space: nowrap;
}

.list {
  display: flex;
  flex-direction: column;
  width: 240px;
}

.list-empty {
  padding: vars.$padding-1;
  font-size: 0.75rem;
  color: colors.$display;
}`,
  },
  {
    name: "辞書の検索と同時登録（検索欄の入力欄）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `import BaseButton from "@/components/Base/BaseButton.vue";`,
    patched: `import BaseButton from "@/components/Base/BaseButton.vue";
import BaseTextField from "@/components/Base/BaseTextField.vue";`,
  },
  {
    name: "同時登録の状態を単語エディタへ渡す",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `            :initialWordPriority="currentWord.wordPriority"
            :initialAccentType="currentWord.accentType"
          />`,
    patched: `            :initialWordPriority="currentWord.wordPriority"
            :initialAccentType="currentWord.accentType"
            :initialSplitRegistered="
              isSplitRegistered(wordSplits, currentWord.surface)
            "
            :initialSplitValue="wordSplits[currentWord.surface]"
          />`,
  },
  {
    name: "同時登録の既定を新しい単語へ渡す",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `            :initialWordPriority="5"
            :initialAccentType="0"
            isNew`,
    patched: `            :initialWordPriority="5"
            :initialAccentType="0"
            :initialSplitRegistered="true"
            isNew`,
  },
  {
    name: "同時登録の処理",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `const loadUserDict = async () => {
  if (store.state.engineIds.length === 0)
    throw new Error(\`assert engineId.length > 0\`);
`,
    patched: `/** 分割辞書を読む。読めなくても読み方の登録そのものは続けられる。 */
const loadWordSplits = async () => {
  const engine = dictEngine();
  if (!engine) return;
  try {
    wordSplits.value = await fetchWordSplits(engine);
  } catch (e) {
    // 同時登録の状態が分からないだけなので、空として扱って先へ進む。書き込む前には
    // 必ず読み直すため、ここで空になっても登録済みの分割を消すことはない。
    wordSplits.value = {};
    window.backend.logError(e);
  }
};

/**
 * 分割辞書へ、いまの登録内容を反映する。
 *
 * エンジンには 1 語だけを足す口が無く、送った一覧がそのまま辞書になる。書き込む直前に
 * 必ず取り直し、取れなければ何も送らない。手元の古い一覧を送ると、辞書画面を開いた後に
 * 別の場所で足された語が消える。
 */
const applySplitPlan = async (
  plan: (splits: WordSplits) => WordSplits | undefined,
) => {
  const engine = dictEngine();
  if (!engine) return;

  try {
    const latest = await lockUiWhile(fetchWordSplits(engine));
    const next = plan(latest);
    if (next == undefined) {
      wordSplits.value = latest;
      return;
    }
    await lockUiWhile(sendWordSplits(engine, next));
    wordSplits.value = next;
  } catch (e) {
    const detail =
      e instanceof Error ? e.message : "更新の途中で失敗しました。";
    alertDict(
      "フレーズ分割辞書を更新できませんでした",
      \`\${detail}\\n読み方＆アクセント辞書への登録は保存されています。\`,
    );
    window.backend.logError(e);
  }
};

/** 登録した単語を分割辞書へ通す。表記を変えたときは前の表記の分も片付ける。 */
const linkWordSplit = (params: {
  previousSurface?: string;
  surface: string;
  registered: boolean;
}) => applySplitPlan((splits) => planSplitLink({ splits, ...params }));

/** 削除した単語の分割を片付ける。手で区切りを直した内容は残す。 */
const unlinkWordSplit = (surface: string) =>
  applySplitPlan((splits) => planSplitUnlink({ splits, surface }));

const loadUserDict = async () => {
  if (store.state.engineIds.length === 0)
    throw new Error(\`assert engineId.length > 0\`);

  await loadWordSplits();
`,
  },
  {
    name: "同時登録（単語の変更時）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `    userDict.value[currentWord.value.id] = {
      ...userDict.value[currentWord.value.id],`,
    patched: `    await linkWordSplit({
      previousSurface: currentWord.value.surface,
      surface: editState.surface,
      registered: editState.splitRegistered,
    });
    userDict.value[currentWord.value.id] = {
      ...userDict.value[currentWord.value.id],`,
  },
  {
    name: "同時登録（単語の追加時）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `    await loadUserDict();
    selectWord(wordUuid);`,
    patched: `    await linkWordSplit({
      surface: editState.surface,
      registered: editState.splitRegistered,
    });
    // 絞り込みに一致しない語を足すと、登録できたのに一覧から消えたように見える。
    const shown = matcher.value;
    if (
      shown.type === "matcher" &&
      !shown.matches([editState.surface, editState.yomi])
    ) {
      searchQuery.value = "";
    }
    await loadUserDict();
    selectWord(wordUuid);`,
  },
  {
    name: "同時登録（単語の削除時）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `      await lockUiWhile(
        store.actions.DELETE_WORD({
          wordUuid: id,
        }),
      );`,
    patched: `      const deletedSurface = userDict.value[id].surface;
      await lockUiWhile(
        store.actions.DELETE_WORD({
          wordUuid: id,
        }),
      );
      await unlinkWordSplit(deletedSurface);`,
  },
  {
    name: "辞書を開いたときに検索を戻す",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "DictionaryManageDialog.vue"),
    original: `      await loadUserDict();
      currentWord.value = null;
    }`,
    patched: `      searchQuery.value = "";
      await loadUserDict();
      currentWord.value = null;
    }`,
  },
  {
    name: "同時登録の欄（読み込み）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `import BaseButton from "@/components/Base/BaseButton.vue";`,
    patched: `import BaseButton from "@/components/Base/BaseButton.vue";
import BaseCheckbox from "@/components/Base/BaseCheckbox.vue";
import { autoSplitValue } from "@/domain/dictSplitLink";`,
  },
  {
    name: "同時登録の欄（プロパティ）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `    initialWordPriority: number;
    initialAccentType: number;
  }>(),`,
    patched: `    initialWordPriority: number;
    initialAccentType: number;
    /** フレーズ分割辞書へ同時登録するか。新しい単語では登録する側を既定にする。 */
    initialSplitRegistered: boolean;
    /** 分割辞書に既にある分割後の文字列。無ければ未登録。 */
    initialSplitValue?: string;
  }>(),`,
  },
  {
    name: "同時登録の欄（プロパティの既定値）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `  {
    isNew: false,
  },
);`,
    patched: `  {
    isNew: false,
    initialSplitValue: undefined,
  },
);`,
  },
  {
    name: "同時登録の欄（状態）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `const wordPriority = ref<number>(props.initialWordPriority);`,
    patched: `const wordPriority = ref<number>(props.initialWordPriority);
const splitRegistered = ref<boolean>(props.initialSplitRegistered);

/**
 * 分割辞書へ書き込まれる内容。
 *
 * 既に手で区切りを直した内容があるなら、それをそのまま使う（同時登録は上書きしない）。
 * 表記を変えた場合は前の分割が当てはまらないため、新しい表記から組んだ形を出す。
 */
const splitValue = computed(() =>
  surface.value === props.initialSurface && props.initialSplitValue != undefined
    ? props.initialSplitValue
    : autoSplitValue(surface.value),
);`,
  },
  {
    name: "同時登録の欄（編集状態の型）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `          type: "valid";
          surface: string;
          yomi: string;
          accentType: number;
          wordPriority: number;
        } => {`,
    patched: `          type: "valid";
          surface: string;
          yomi: string;
          accentType: number;
          wordPriority: number;
          splitRegistered: boolean;
        } => {`,
  },
  {
    name: "同時登録の欄（変更の判定）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `            accentType === props.initialAccentType &&
            wordPriority.value === props.initialWordPriority`,
    patched: `            accentType === props.initialAccentType &&
            wordPriority.value === props.initialWordPriority &&
            splitRegistered.value === props.initialSplitRegistered`,
  },
  {
    name: "同時登録の欄（編集状態の値）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `        accentType: computeRegisteredAccent(),
        wordPriority: wordPriority.value,
      };`,
    patched: `        accentType: computeRegisteredAccent(),
        wordPriority: wordPriority.value,
        splitRegistered: splitRegistered.value,
      };`,
  },
  {
    name: "同時登録の欄（リセット）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `  wordPriority.value = props.initialWordPriority;
  temporaryYomi.value = props.initialYomi;`,
    patched: `  wordPriority.value = props.initialWordPriority;
  splitRegistered.value = props.initialSplitRegistered;
  temporaryYomi.value = props.initialYomi;`,
  },
  {
    name: "同時登録の欄（画面）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `            <div class="slider-label">
              <span>低い</span>
              <span>標準</span>
              <span>高い</span>
            </div>
          </div>
        </div>
      </div>
    </BaseScrollArea>`,
    patched: `            <div class="slider-label">
              <span>低い</span>
              <span>標準</span>
              <span>高い</span>
            </div>
          </div>
        </div>
        <div class="form-row">
          <h3 class="headline">フレーズ分割辞書への同時登録</h3>
          <div>
            この単語をフレーズ分割辞書へも登録し、単語の前後をフレーズの区切りにします。
            「証券取引所」のように解析がひとまとまりとして扱う複合語の内側にある単語でも、
            登録した読みとアクセントが反映されるようになります。
          </div>
          <div>
            区切りでポーズ（無音）は入りません。ただし短い単語では読みが細かく分かれて
            聞こえることがあるため、その場合はオフにしてください。
          </div>
          <div class="split-toggle">
            <BaseCheckbox
              v-model:checked="splitRegistered"
              label="フレーズ分割辞書にも登録する"
            />
          </div>
          <div v-if="splitRegistered && surface.length > 0" class="split-value">
            登録される内容: {{ splitValue }}
          </div>
        </div>
      </div>
    </BaseScrollArea>`,
  },
  {
    name: "同時登録の欄（見た目）",
    file: join(editorSrc, "components", "Dialog", "DictionaryManageDialog", "WordEditor.vue"),
    original: `.slider-label {
  display: flex;
  justify-content: space-between;
}`,
    patched: `.slider-label {
  display: flex;
  justify-content: space-between;
}

/* チェックボックスは中央寄せで作られているため、フォームの左端へ揃え直す。 */
.split-toggle {
  display: flex;
}

.split-value {
  color: colors.$display;
  word-break: break-all;
}`,
  },
  {
    name: "保存先を開く IPC の宣言",
    file: join(editorSrc, "backend", "electron", "ipcType.ts"),
    original: `  OPEN_ENGINE_DIRECTORY: {
    args: [obj: { engineId: EngineId }];
    return: void;
  };
`,
    patched: `  OPEN_ENGINE_DIRECTORY: {
    args: [obj: { engineId: EngineId }];
    return: void;
  };

  OPEN_CONTAINING_FOLDER: {
    args: [obj: { filePath: string }];
    return: void;
  };
`,
  },
  {
    name: "保存先を開く処理",
    file: join(editorSrc, "backend", "electron", "manager", "ipcMainHandleManager.ts"),
    original: `  void shell.openPath(path.resolve(engineDirectory));
}
`,
    patched: `  void shell.openPath(path.resolve(engineDirectory));
}

// 書き出したファイルを選択した状態で、その置き場所を開く
function openContainingFolder(filePath: string) {
  // Windows環境だとスラッシュ区切りのパスが動かない。
  // path.resolveはWindowsだけバックスラッシュ区切りにしてくれるため、path.resolveを挟む。
  const resolved = path.resolve(filePath);

  // 通知が消えるまでの間に移動・削除された場合は何もしない。
  if (!fs.existsSync(resolved)) return;

  shell.showItemInFolder(resolved);
}
`,
  },
  {
    name: "保存先を開く IPC の登録",
    file: join(editorSrc, "backend", "electron", "manager", "ipcMainHandleManager.ts"),
    original: `      OPEN_ENGINE_DIRECTORY: async (_, { engineId }) => {
        openEngineDirectory(engineId);
      },
`,
    patched: `      OPEN_ENGINE_DIRECTORY: async (_, { engineId }) => {
        openEngineDirectory(engineId);
      },

      OPEN_CONTAINING_FOLDER: async (_, { filePath }) => {
        openContainingFolder(filePath);
      },
`,
  },
  {
    name: "保存先を開く橋渡し",
    file: join(editorSrc, "backend", "electron", "renderer", "preload.ts"),
    original: `  openEngineDirectory: (engineId: EngineId) => {
    return ipcRendererInvokeProxy.OPEN_ENGINE_DIRECTORY({ engineId });
  },
`,
    patched: `  openEngineDirectory: (engineId: EngineId) => {
    return ipcRendererInvokeProxy.OPEN_ENGINE_DIRECTORY({ engineId });
  },

  openContainingFolder: (filePath: string) => {
    return ipcRendererInvokeProxy.OPEN_CONTAINING_FOLDER({ filePath });
  },
`,
  },
  {
    name: "保存先を開く口の型",
    file: join(editorSrc, "type", "preload.ts"),
    original: `  openEngineDirectory(engineId: EngineId): void;
`,
    patched: `  openEngineDirectory(engineId: EngineId): void;
  openContainingFolder(filePath: string): void;
`,
  },
  {
    name: "保存先を開く口（ブラウザ版）",
    file: join(editorSrc, "backend", "browser", "sandbox.ts"),
    original: `  openEngineDirectory(/* engineId: EngineId */) {
    throw new Error(\`Not supported on Browser version: openEngineDirectory\`);
  },
`,
    patched: `  openEngineDirectory(/* engineId: EngineId */) {
    throw new Error(\`Not supported on Browser version: openEngineDirectory\`);
  },
  openContainingFolder(/* filePath: string */) {
    throw new Error(\`Not supported on Browser version: openContainingFolder\`);
  },
`,
  },
  {
    name: "保存先を開く操作の型",
    file: join(editorSrc, "store", "type.ts"),
    original: `  SHOW_NOTIFY_AND_NOT_SHOW_AGAIN_BUTTON: {
    action(payload: NotifyAndNotShowAgainButtonOption): void;
  };
`,
    patched: `  SHOW_NOTIFY_AND_NOT_SHOW_AGAIN_BUTTON: {
    action(payload: NotifyAndNotShowAgainButtonOption): void;
  };

  OPEN_CONTAINING_FOLDER: {
    action(payload: { filePath: string }): void;
  };
`,
  },
  {
    name: "保存先を開く操作",
    file: join(editorSrc, "store", "ui.ts"),
    original: `  SHOW_NOTIFY_AND_NOT_SHOW_AGAIN_BUTTON: {
    action({ actions }, payload: NotifyAndNotShowAgainButtonOption) {
      showNotifyAndNotShowAgainButton({ actions }, payload);
    },
  },
`,
    patched: `  SHOW_NOTIFY_AND_NOT_SHOW_AGAIN_BUTTON: {
    action({ actions }, payload: NotifyAndNotShowAgainButtonOption) {
      showNotifyAndNotShowAgainButton({ actions }, payload);
    },
  },

  OPEN_CONTAINING_FOLDER: {
    action(_, { filePath }) {
      window.backend.openContainingFolder(filePath);
    },
  },
`,
  },
  {
    name: "書き出し通知の動作環境の判定",
    file: join(editorSrc, "components", "Dialog", "Dialog.ts"),
    original: `import { errorToMessage } from "@/helpers/errorHelper";
`,
    patched: `import { errorToMessage } from "@/helpers/errorHelper";
import { isElectron } from "@/helpers/platform";
`,
  },
  {
    name: "書き出し通知のボタン",
    file: join(editorSrc, "components", "Dialog", "Dialog.ts"),
    original: `// 書き出し成功時の通知を表示
const showWriteSuccessNotify = ({
  mediaType,
  actions,
}: {
  mediaType: MediaType;
  actions: DotNotationDispatch<AllActions>;
}): void => {
  const mediaTypeNames: Record<MediaType, string> = {
    audio: "音声",
    text: "テキスト",
    project: "プロジェクト",
    label: "labファイル",
  };
  void actions.SHOW_NOTIFY_AND_NOT_SHOW_AGAIN_BUTTON({
    message: \`\${mediaTypeNames[mediaType]}を書き出しました\`,
    tipName: "notifyOnGenerate",
  });
};
`,
    patched: `// 書き出し成功時の通知を表示
const showWriteSuccessNotify = ({
  mediaType,
  savedPath,
  actions,
}: {
  mediaType: MediaType;
  savedPath: string | undefined;
  actions: DotNotationDispatch<AllActions>;
}): void => {
  const mediaTypeNames: Record<MediaType, string> = {
    audio: "音声",
    text: "テキスト",
    project: "プロジェクト",
    label: "labファイル",
  };

  // 保存先が分かっていて、かつフォルダを開ける環境のときだけ導線を出す。
  // ブラウザ版には開く手段が無いため、押せないボタンを見せない。
  const openFolderActions =
    isElectron && savedPath != undefined
      ? [
          {
            label: "保存されたフォルダを開く",
            textColor: "toast-button-display",
            handler: () => {
              void actions.OPEN_CONTAINING_FOLDER({ filePath: savedPath });
            },
          },
        ]
      : [];

  Notify.create({
    message: \`\${mediaTypeNames[mediaType]}を書き出しました\`,
    color: "toast",
    textColor: "toast-display",
    icon: "info",
    timeout: NOTIFY_TIMEOUT,
    actions: [
      ...openFolderActions,
      {
        label: "閉じる",
        color: "toast-button-display",
      },
    ],
  });
};
`,
  },
  {
    name: "書き出し通知へ渡す保存先（まとめて書き出し）",
    file: join(editorSrc, "components", "Dialog", "Dialog.ts"),
    original: `    showWriteSuccessNotify({
      mediaType: "audio",
      actions,
    });`,
    patched: `    showWriteSuccessNotify({
      mediaType: "audio",
      savedPath: successArray[0],
      actions,
    });`,
  },
  {
    name: "書き出し通知へ渡す保存先（1 件の書き出し）",
    file: join(editorSrc, "components", "Dialog", "Dialog.ts"),
    original: `    showWriteSuccessNotify({
      mediaType,
      actions,
    });`,
    patched: `    showWriteSuccessNotify({
      mediaType,
      savedPath: result.path,
      actions,
    });`,
  },
  {
    name: "辞書更新時にキャッシュを捨てる口",
    file: join(editorSrc, "store", "audioGenerate.ts"),
    original: `const audioBlobCache: Record<string, Blob> = {};
`,
    patched: `const audioBlobCache: Record<string, Blob> = {};

/**
 * 合成済みの音声を捨てる。
 *
 * キャッシュの鍵は本文・クエリ・話者から作るため、辞書を書き換えても鍵が変わらない。
 * 捨てないと、登録したのに前の読みで作った音がそのまま再生される。
 */
export function clearAudioBlobCache(): void {
  for (const key of Object.keys(audioBlobCache)) {
    delete audioBlobCache[key];
  }
}
`,
  },
  {
    name: "辞書更新時の取り直しの読み込み",
    file: join(editorSrc, "store", "audio.ts"),
    original: `import {
  fetchAudioFromAudioItem,
  generateLabFromAudioQuery,
  handlePossiblyNotMorphableError,
  isMorphable,
} from "./audioGenerate";
`,
    patched: `import {
  clearAudioBlobCache,
  fetchAudioFromAudioItem,
  generateLabFromAudioQuery,
  handlePossiblyNotMorphableError,
  isMorphable,
} from "./audioGenerate";
`,
  },
  {
    name: "辞書更新時の取り直し",
    file: join(editorSrc, "store", "audio.ts"),
    original: `  FETCH_AUDIO: {
`,
    patched: `  INVALIDATE_DICTIONARY_DEPENDENT_AUDIO: {
    action: createUILockAction(async ({ state, mutations, actions }) => {
      // 合成済みの音声は辞書を当てたあとの読みで作られている。まず捨てる。
      clearAudioBlobCache();

      // クエリも作り直す。エンジンは送られたアクセント句から本文を組み直すため、
      // 古いクエリを送ると読みが辞書を当てる前へ戻る。画面下のカタカナも古いままになる。
      for (const audioKey of state.audioKeys) {
        const audioItem = state.audioItems[audioKey];
        if (audioItem.query == undefined) continue;
        try {
          const audioQuery = await actions.FETCH_AUDIO_QUERY({
            text: audioItem.text,
            engineId: audioItem.voice.engineId,
            styleId: audioItem.voice.styleId,
          });
          mutations.SET_AUDIO_QUERY({ audioKey, audioQuery });
        } catch (error) {
          // 1 行取れなくても残りは作り直す。取れなかった行は次に触ったときに揃う。
          window.backend.logError(error);
        }
      }
    }),
  },

  FETCH_AUDIO: {
`,
  },
  {
    name: "辞書更新時の取り直しの型",
    file: join(editorSrc, "store", "type.ts"),
    original: `  FETCH_AUDIO_QUERY: {
    action(payload: {
      text: string;
      engineId: EngineId;
`,
    patched: `  INVALIDATE_DICTIONARY_DEPENDENT_AUDIO: {
    action(): void;
  };

  FETCH_AUDIO_QUERY: {
    action(payload: {
      text: string;
      engineId: EngineId;
`,
  },
  {
    name: "単語を足したときの取り直し",
    file: join(editorSrc, "store", "dictionary.ts"),
    original: `      await actions.SYNC_ALL_USER_DICT();
      return wordUuid;
`,
    patched: `      await actions.SYNC_ALL_USER_DICT();
      await actions.INVALIDATE_DICTIONARY_DEPENDENT_AUDIO();
      return wordUuid;
`,
  },
  {
    name: "単語を書き換えたときの取り直し",
    file: join(editorSrc, "store", "dictionary.ts"),
    original: `            instance.invoke("rewriteUserDictWord")({
              wordUuid,
              surface,
              pronunciation,
              accentType,
              priority,
            }),
          );
      }
    },
  },
`,
    patched: `            instance.invoke("rewriteUserDictWord")({
              wordUuid,
              surface,
              pronunciation,
              accentType,
              priority,
            }),
          );
      }
      await actions.INVALIDATE_DICTIONARY_DEPENDENT_AUDIO();
    },
  },
`,
  },
  {
    name: "単語を消したときの取り直し",
    file: join(editorSrc, "store", "dictionary.ts"),
    original: `            instance.invoke("deleteUserDictWord")({
              wordUuid,
            }),
          );
      }
    },
  },
`,
    patched: `            instance.invoke("deleteUserDictWord")({
              wordUuid,
            }),
          );
      }
      await actions.INVALIDATE_DICTIONARY_DEPENDENT_AUDIO();
    },
  },
`,
  },
];
