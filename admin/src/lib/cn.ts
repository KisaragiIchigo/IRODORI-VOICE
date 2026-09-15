/** クラス名の結合。falsy を落として空白で繋ぐだけ。 */
export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}
