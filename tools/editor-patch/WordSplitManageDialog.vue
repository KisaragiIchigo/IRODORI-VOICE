<template>
  <QDialog
    v-model="dialogOpened"
    maximized
    transitionShow="jump-up"
    transitionHide="jump-down"
    class="setting-dialog transparent-backdrop"
    persistent
  >
    <QLayout>
      <QPageContainer>
        <QHeader class="q-pa-sm">
          <QToolbar>
            <QToolbarTitle class="text-display">フレーズ分割辞書</QToolbarTitle>
            <QSpace />
            <QBtn
              flat
              dense
              noCaps
              icon="file_download"
              label="書き出し"
              color="display"
              @click="exportSplits"
            />
            <QBtn
              flat
              dense
              noCaps
              icon="file_upload"
              label="取り込み"
              color="display"
              @click="importSplits"
            />
            <QBtn
              round
              flat
              icon="close"
              color="display"
              @click="dialogOpened = false"
            />
          </QToolbar>
        </QHeader>

        <BaseNavigationView>
          <template #sidebar>
            <div class="list-header">
              <div class="list-title">単語一覧</div>
              <BaseButton label="追加" icon="add" @click="selectNewWord" />
            </div>
            <div class="search">
              <BaseTextField
                v-model="searchQuery"
                ariaLabel="単語を検索"
                placeholder="単語・分割後の文字列で検索"
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
                v-for="[target, replace] in filteredSplits"
                :key="target"
                :selected="currentWord === target"
                @click="currentWord = target"
                @mouseover="hoveredKey = target"
                @mouseleave="hoveredKey = undefined"
              >
                <div class="listitem">
                  <div class="listitem-text">
                    <span class="listitem-surface">{{ target }}</span>
                    <span class="listitem-yomi">{{ replace }}</span>
                  </div>
                  <BaseIconButton
                    v-if="hoveredKey === target || currentWord === target"
                    icon="delete_outline"
                    label="削除"
                    @click.stop="deleteSplit(target)"
                  />
                </div>
              </BaseListItem>
              <div v-if="filteredSplits.length === 0" class="list-empty">
                {{
                  Object.keys(splits).length === 0
                    ? "まだ単語が登録されていません。"
                    : "検索に一致する単語がありません。"
                }}
              </div>
            </div>
          </template>

          <div v-if="currentWord != undefined" class="detail">
            <div class="inner">
              <div class="title">
                {{ isNew ? "新しい単語を追加" : "単語を編集" }}
              </div>

              <div class="form-row q-mt-md">
                <h3 class="headline">対象の単語（変換前）</h3>
                <div class="subtext text-caption">例: 台湾証券取引所</div>
                <BaseTextField
                  v-model="editTarget"
                  ariaLabel="対象の単語"
                  class="input q-mt-sm"
                  :disabled="!isNew"
                />
              </div>

              <div class="form-row q-mt-md">
                <h3 class="headline">分割後の文字列（変換後）</h3>
                <div class="subtext text-caption">
                  ・間に「読点（、）」を入れると、無音のポーズ（息継ぎ）が入ります。<br />
                  ・間に「アンダースコア（_）」を入れると、ポーズを空けずにフレーズだけを分割します。
                </div>
                <BaseTextField
                  v-model="editReplace"
                  ariaLabel="分割後の文字列"
                  class="input q-mt-sm"
                />
              </div>

              <div class="q-mt-xl">
                <BaseButton
                  label="保存"
                  :disabled="!editTarget || !editReplace"
                  @click="saveCurrentSplit"
                />
              </div>
            </div>
          </div>
          <div v-else class="detail flex flex-center">
            <div class="text-h6 subtext">
              単語を選択するか、新しく追加してください。
            </div>
          </div>
        </BaseNavigationView>
      </QPageContainer>
    </QLayout>
  </QDialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import BaseNavigationView from "@/components/Base/BaseNavigationView.vue";
import BaseButton from "@/components/Base/BaseButton.vue";
import BaseListItem from "@/components/Base/BaseListItem.vue";
import BaseIconButton from "@/components/Base/BaseIconButton.vue";
import BaseTextField from "@/components/Base/BaseTextField.vue";
import BaseCheckbox from "@/components/Base/BaseCheckbox.vue";
import { useStore } from "@/store";
import {
  type WordSplits,
  fetchWordSplits,
  readWordSplitsFile,
  sendWordSplits,
} from "@/domain/wordSplits";
import { createDictMatcher } from "@/domain/dictSearch";

const props = defineProps<{ dialogOpened: boolean }>();
const emit = defineEmits(["update:dialogOpened"]);

const store = useStore();

const dialogOpened = computed({
  get: () => props.dialogOpened,
  set: (val) => emit("update:dialogOpened", val),
});

const splits = ref<WordSplits>({});
const hoveredKey = ref<string | undefined>();
const currentWord = ref<string | undefined>();
const isNew = ref(false);
const editTarget = ref("");
const editReplace = ref("");
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

/** 一覧に出す単語。単語と分割後の文字列の両方を照合に使う。 */
const filteredSplits = computed<[string, string][]>(() => {
  const entries = Object.entries(splits.value);
  const current = matcher.value;
  // 正規表現が書き損じの間は絞り込まない。入力の途中で一覧が消えると、何を直せば
  // よいのか分からなくなる。理由は検索欄の下に出す。
  if (current.type !== "matcher") return entries;
  return entries.filter(([target, replace]) =>
    current.matches([target, replace]),
  );
});

const searchCount = computed(() => {
  const total = Object.keys(splits.value).length;
  const shown = filteredSplits.value.length;
  return shown === total ? `${total} 件` : `${shown} / ${total} 件`;
});

/** 分割辞書のやり取りに使うエンジン。1 つ目のエンジンが辞書の持ち主になる。 */
const splitEngine = () => store.getters.GET_SORTED_ENGINE_INFOS[0];

const alertSplit = (title: string, message: string) => {
  void store.actions.SHOW_ALERT_DIALOG({ title, message });
};

async function loadSplits() {
  const engine = splitEngine();
  if (!engine) {
    alertSplit(
      "分割辞書を読み込めませんでした",
      "エンジンに接続できていません。",
    );
    return;
  }

  try {
    splits.value = await fetchWordSplits(engine);
  } catch (e) {
    alertSplit(
      "分割辞書を読み込めませんでした",
      e instanceof Error ? e.message : "読み込みの途中で失敗しました。",
    );
    window.backend.logError(e);
  }
}

/** 一覧を丸ごと入れ替える。保存できたかを返す。 */
async function saveSplits(newSplits: WordSplits): Promise<boolean> {
  const engine = splitEngine();
  if (!engine) {
    alertSplit(
      "分割辞書を保存できませんでした",
      "エンジンに接続できていません。",
    );
    return false;
  }

  try {
    await sendWordSplits(engine, newSplits);
    // 区切りが変われば読みも変わる。合成済みの音声とクエリを作り直す。
    await store.actions.INVALIDATE_DICTIONARY_DEPENDENT_AUDIO();
  } catch (e) {
    alertSplit(
      "分割辞書を保存できませんでした",
      e instanceof Error ? e.message : "保存の途中で失敗しました。",
    );
    window.backend.logError(e);
    return false;
  }

  await loadSplits();
  return true;
}

function selectNewWord() {
  currentWord.value = "__NEW__";
}

async function saveCurrentSplit() {
  if (!editTarget.value || !editReplace.value) return;

  // 新しく追加するとき、同じ単語が既にあれば黙って置き換えない。一覧は 50 音順でも
  // 登録順でもないため、打ち込んだ単語が既にあることに気づけないまま上書きしうる。
  if (isNew.value && editTarget.value in splits.value) {
    const result = await store.actions.SHOW_WARNING_DIALOG({
      title: "同じ単語が既に登録されています",
      message: `「${editTarget.value}」の分割後の文字列を、いま入力した内容へ置き換えます。`,
      actionName: "置き換える",
      cancel: "やめる",
      isWarningColorButton: true,
    });
    if (result !== "OK") return;
  }

  const current = { ...splits.value };
  current[editTarget.value] = editReplace.value;
  // 保存できていないのに選択を移すと、watch が編集中の内容を空へ戻してしまう。
  if (await saveSplits(current)) {
    currentWord.value = editTarget.value;
    // 絞り込みに一致しない語を保存すると、保存できたのに一覧から消えたように見える。
    const shown = matcher.value;
    if (
      shown.type === "matcher" &&
      !shown.matches([editTarget.value, editReplace.value])
    ) {
      searchQuery.value = "";
    }
  }
}

async function deleteSplit(target: string) {
  const current = { ...splits.value };
  delete current[target];
  if (!(await saveSplits(current))) return;
  if (currentWord.value === target) {
    currentWord.value = undefined;
  }
}

function exportSplits() {
  if (Object.keys(splits.value).length === 0) {
    alertSplit(
      "分割辞書を書き出せませんでした",
      "分割辞書にはまだ単語が 1 つも登録されていません。",
    );
    return;
  }

  const data = JSON.stringify(splits.value, undefined, 2);
  const blob = new Blob([data], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "word_splits.json";
  a.click();
  URL.revokeObjectURL(url);
}

function importSplits() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;

    let parsed: WordSplits;
    try {
      parsed = readWordSplitsFile(await file.text());
    } catch (e) {
      alertSplit(
        "分割辞書を取り込めませんでした",
        e instanceof Error ? e.message : "ファイルを読めませんでした。",
      );
      return;
    }

    // 取り込んだ語で一覧が入れ替わるため、編集していた語の選択は外す。
    if (await saveSplits(parsed)) {
      currentWord.value = undefined;
      alertSplit(
        "分割辞書を取り込みました",
        `${Object.keys(parsed).length} 語を取り込みました。`,
      );
    }
  };
  input.click();
}

watch(dialogOpened, (newVal) => {
  if (newVal) {
    void loadSplits();
    currentWord.value = undefined;
    searchQuery.value = "";
  }
});

watch(currentWord, (target) => {
  if (target === "__NEW__") {
    isNew.value = true;
    editTarget.value = "";
    editReplace.value = "";
  } else if (target) {
    isNew.value = false;
    editTarget.value = target;
    editReplace.value = splits.value[target] || "";
  } else {
    isNew.value = false;
    editTarget.value = "";
    editReplace.value = "";
  }
});
</script>

<style lang="scss" scoped>
@use "@/styles/colors" as colors;
@use "@/styles/v2/variables" as vars;
@use "@/styles/v2/mixin" as mixin;

.list-header {
  display: flex;
  gap: vars.$gap-1;
  align-items: center;
  justify-content: space-between;
  margin-bottom: vars.$padding-1;
}

.list-title {
  @include mixin.headline-2;
}

.search {
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
  color: var(--color-display);
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
  color: var(--color-display);
}

.listitem {
  display: flex;
  align-items: center;
  gap: vars.$gap-1;
  width: 100%;
}

.listitem-text {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.listitem-surface {
  width: 100%;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.listitem-yomi {
  width: 100%;
  font-size: 0.75rem;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.detail {
  display: flex;
  flex-flow: column;
  height: 100%;
}

.inner {
  min-height: 100%;
  max-width: 960px;
  margin: auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  padding: vars.$padding-2;
  gap: vars.$gap-2;
}

.title {
  @include mixin.headline-1;
  word-break: break-all;
}

.form-row {
  display: flex;
  flex-flow: column;
  gap: vars.$gap-1;
}

.headline {
  @include mixin.headline-2;
  margin: 0;
}

.subtext {
  color: var(--color-display);
  opacity: 0.6;
}
</style>
