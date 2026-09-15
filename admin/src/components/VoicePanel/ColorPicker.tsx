import { cn } from "../../lib/cn";
import { VOICE_COLORS, VOICE_COLOR_HEX } from "../../lib/types";

type Props = {
  value: string;
  onChange: (key: string) => void;
};

/** 話者の識別色。エディタの一覧で見分けるための印なので、被っても構わない。 */
export function ColorPicker({ value, onChange }: Props) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="label-caps">識別色</span>
      <div className="flex flex-wrap gap-2">
        {VOICE_COLORS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-label={key}
            className={cn(
              "h-7 w-7 rounded-full border transition-transform",
              value === key ? "border-white/40 scale-110" : "border-white/[0.08] hover:scale-105",
            )}
            style={{
              backgroundColor: VOICE_COLOR_HEX[key],
              boxShadow: value === key ? `0 0 12px ${VOICE_COLOR_HEX[key]}66` : undefined,
            }}
          />
        ))}
      </div>
    </div>
  );
}
