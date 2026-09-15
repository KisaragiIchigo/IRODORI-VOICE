import { m } from "framer-motion";
import { Plus } from "lucide-react";

type Props = {
  onClick: () => void;
  disabled: boolean;
};

/** 一覧の末尾に置く追加口。ここへ落とせることも、並びの中で示しておく。 */
export function AddTile({ onClick, disabled }: Props) {
  return (
    <m.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : { scale: 1.006 }}
      whileTap={disabled ? undefined : { scale: 0.99 }}
      transition={{ type: "spring", stiffness: 420, damping: 30 }}
      className="flex min-h-[9rem] flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-white/[0.1] bg-white/[0.01] px-4 py-6 text-center transition-colors hover:border-beni/40 hover:bg-beni/[0.04] disabled:opacity-40"
    >
      <Plus className="h-4 w-4 text-paper-400" />
      <span className="text-body text-paper-200">モデルを追加</span>
      <span className="text-label leading-relaxed text-paper-400">
        ファイルをこの画面へ落としても取り込めます
      </span>
    </m.button>
  );
}
