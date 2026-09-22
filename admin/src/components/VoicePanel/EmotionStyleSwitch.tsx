import * as Switch from "@radix-ui/react-switch";

import { cn } from "../../lib/cn";

/** エンジンの voices/expression_styles.py が持つ顔ぶれ。ノーマルを除いた数を出す。 */
const EMOTION_STYLE_NAMES = [
  "あかるい",
  "よろこび",
  "やさしさ",
  "あんど",
  "じしん",
  "からかい",
  "かんがえ",
  "かんたん",
  "おどろき",
  "てれ",
  "ふあん",
  "あせり",
  "くるしげ",
  "おこり",
  "あきれ",
  "ねむそう",
  "よい",
  "ちからづよく",
  "おねがい",
  "ろうどく",
  "かなしみ",
  "まじめ",
  "ゆっくり",
  "はやくち",
] as const;

type Props = {
  checked: boolean;
  onChange: (next: boolean) => void;
};

/** 喜怒哀楽のスタイルを付けるかの切り替え。声の作り方が違っても、付く顔ぶれは同じ。 */
export function EmotionStyleSwitch({ checked, onChange }: Props) {
  return (
    <label className="flex items-start gap-3 rounded-md border border-white/[0.04] bg-black/20 px-3 py-2.5">
      <Switch.Root
        checked={checked}
        onCheckedChange={onChange}
        className={cn(
          "relative mt-0.5 h-5 w-9 shrink-0 rounded-full border transition-colors",
          checked
            ? "border-beni/40 bg-beni/30 shadow-glow"
            : "border-white/[0.08] bg-white/[0.04]",
        )}
      >
        <Switch.Thumb
          className={cn(
            "block h-3.5 w-3.5 rounded-full bg-paper-200 transition-transform",
            "translate-x-1 data-[state=checked]:translate-x-[1.15rem]",
          )}
        />
      </Switch.Root>
      <span className="flex flex-col gap-0.5">
        <span className="text-body text-paper-200">喜怒哀楽のスタイルも作る</span>
        <span className="text-label leading-relaxed text-paper-400">
          {EMOTION_STYLE_NAMES.join("・")}の {EMOTION_STYLE_NAMES.length} 種類を追加します。
          同じ声のまま口調を変えられます。なお、この喋り分けは標準チェックポイントでのみ効きます。
        </span>
      </span>
    </label>
  );
}
