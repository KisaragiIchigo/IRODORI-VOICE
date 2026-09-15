import { ref } from "vue";

/**
 * 「音声モデルの管理」ダイアログの開閉。
 *
 * VOICEVOX の store（SET_DIALOG_OPEN）へ項目を足すと本家のソースを広く触ることになるため、
 * この画面の状態だけを独立して持つ。メニュー側とダイアログ側の両方から参照する。
 */
export const isAdminDialogOpen = ref(false);
