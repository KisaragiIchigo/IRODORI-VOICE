<template>
  <QDialog
    v-model="isAdminDialogOpen"
    maximized
    allowFocusOutside
    transitionShow="jump-up"
    transitionHide="jump-down"
    class="admin-dialog transparent-backdrop"
    @hide="reloadCharacters"
  >
    <div class="admin-shell">
      <div class="admin-bar">
        <span class="admin-title">音声モデルの管理</span>
        <QSpace />
        <QBtn
          round
          flat
          dense
          icon="refresh"
          title="再読み込み"
          class="admin-action"
          @click="reload"
        />
        <QBtn
          round
          flat
          dense
          icon="close"
          title="閉じる"
          class="admin-action"
          @click="isAdminDialogOpen = false"
        />
      </div>
      <!-- 画面の実体はエンジンが配信している。ここでは枠を貸すだけにして、
           機能の追加はエンジン側だけで完結するようにしている。 -->
      <iframe
        v-if="isAdminDialogOpen"
        :src="adminUrl"
        class="admin-frame"
        title="音声モデルの管理"
      />
    </div>
  </QDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { isAdminDialogOpen } from "@/components/Dialog/adminDialogState";
import { useStore } from "@/store";

const store = useStore();

/**
 * 読み込みの世代。開くたびと再読み込みのたびに進める。
 *
 * エンジンが配信する画面は、エンジン側を更新すると中身が変わる。しかし
 * Cache-Control が付かない配信では、ブラウザが Last-Modified からの経過時間で
 * 勝手に有効期限を決めてしまい、エディタを起動し直しても古い画面を使い続ける
 * ことがある。URL を毎回変えて、確実に取り直させる。
 */
const generation = ref(0);

/** 画面の配信元。接続しているエンジンから組み立てる。 */
const adminUrl = computed(() => {
  const info = store.getters.GET_SORTED_ENGINE_INFOS[0];
  const base = info
    ? `${info.protocol}//${info.hostname}${info.defaultPort ? `:${info.defaultPort}` : ""}${info.pathname}`
    : "http://127.0.0.1:50121";
  return `${base}/admin/?t=${generation.value}`;
});

watch(
  isAdminDialogOpen,
  (open) => {
    if (open) {
      generation.value = Date.now();
    }
  },
  { immediate: true },
);

// 話者を足した直後など、中身を取り直したいときに使う。
const reload = () => {
  generation.value = Date.now();
};

/**
 * この画面を閉じたら、エディタが持っている話者一覧を取り直す。
 *
 * エディタは起動時に一度だけ /speakers を読む作りで、あとから増えた話者は
 * 起動し直すまで現れない。この画面ではモデルの取り込みと話者の作成ができる
 * ため、閉じた時点で古くなっている可能性がある。
 *
 * 閉じるボタン・ESC・枠の外側のどれで閉じても通るよう、QDialog の hide で受ける。
 * 失敗しても操作の邪魔はしない。取り直せないだけで、起動し直せば反映される。
 */
const reloadCharacters = () => {
  const reload = async () => {
    await Promise.all(
      store.state.engineIds.map((engineId) =>
        store.actions.LOAD_CHARACTER({ engineId }),
      ),
    );
    // 増えた話者は並び順にも既定スタイルにも入っていない。並び順に無い話者は
    // 一覧の先頭へ回って既定の話者になり、既定スタイルが無いままだと
    // テキスト欄の追加と複数行の貼り付けが落ちる。取り直しに続けて登録する。
    await store.actions.REGISTER_NEW_CHARACTERS();
  };
  void reload().catch(() => {
    // 閉じたあとの更新なので、握って進む。
  });
};
</script>

<style scoped lang="scss">
@use "@/styles/v2/variables" as vars;

// NOTE: SettingDialog と同じ事情で、:global にしないと届かない
:global(.admin-dialog) {
  z-index: vars.$z-index-fullscreen-dialog !important;
}

// QLayout は使わない。container 指定の QLayout は .q-layout に min-height しか
// 与えないため、中の iframe が height:100% を解決できず既定の 150px へ潰れる。
// maximized なダイアログは直下の要素へ height:100% を与えるので、ここで受ける。
.admin-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  // 色はプロジェクトルートの project_style.json（palette.base_bg / base_bg_alt）に従う。
  background-color: #0d0e12;
}

.admin-bar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 2px;
  height: 40px;
  padding: 0 6px 0 16px;
  background-color: #08090c;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.admin-title {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: #d4d4d8;
}

.admin-action {
  color: #a1a1aa;

  &:hover {
    color: #e4e4e7;
  }
}

.admin-frame {
  display: block;
  flex: 1;
  min-height: 0;
  width: 100%;
  border: none;
  // 読み込みが終わるまで白が差し込むのを防ぐ。
  background-color: #0d0e12;
}
</style>
