/** 画面へ出す数値の書式。 */

/** バイト数を読める単位へ。桁が変わっても幅が暴れないよう小数を揃える。 */
export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

/** 送信の進み具合。総量が分からないときは割合を返さない。 */
export function formatProgress(loaded: number, total: number): string {
  if (total <= 0) {
    // 最初の通知が届くまでは総量も送信済みも 0。ここで「0 KB」と出しても意味がない。
    return loaded > 0 ? `${formatSize(loaded)} 送信` : "";
  }
  return `${formatSize(loaded)} / ${formatSize(total)}`;
}
