import { m } from "framer-motion";
import { FileUp } from "lucide-react";
import { useEffect, useState } from "react";

type Props = {
  /** 受け取ったファイル。取り込みを始める。 */
  onDrop: (file: File) => void;
  disabled: boolean;
};

/** 画面のどこへ落としても取り込めるようにする覆い。
 *
 * dragenter と dragleave は子要素を跨ぐたびに飛んでくる。数えて釣り合ったときだけ隠す。
 */
export function DropOverlay({ onDrop, disabled }: Props) {
  const [depth, setDepth] = useState(0);

  useEffect(() => {
    if (disabled) {
      return;
    }

    const hasFile = (event: DragEvent) =>
      Array.from(event.dataTransfer?.types ?? []).includes("Files");

    const onEnter = (event: DragEvent) => {
      if (hasFile(event)) setDepth((current) => current + 1);
    };
    const onLeave = () => setDepth((current) => Math.max(0, current - 1));
    const onOver = (event: DragEvent) => {
      if (hasFile(event)) event.preventDefault();
    };
    const onDropped = (event: DragEvent) => {
      if (!hasFile(event)) return;
      event.preventDefault();
      setDepth(0);
      const file = event.dataTransfer?.files?.[0];
      if (file) onDrop(file);
    };

    window.addEventListener("dragenter", onEnter);
    window.addEventListener("dragleave", onLeave);
    window.addEventListener("dragover", onOver);
    window.addEventListener("drop", onDropped);
    return () => {
      window.removeEventListener("dragenter", onEnter);
      window.removeEventListener("dragleave", onLeave);
      window.removeEventListener("dragover", onOver);
      window.removeEventListener("drop", onDropped);
      // 取り込みが始まって覆いを外すとき、数えた分を戻しておく。
      setDepth(0);
    };
  }, [disabled, onDrop]);

  if (depth === 0 || disabled) {
    return null;
  }

  return (
    <m.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.12 }}
      className="pointer-events-none fixed inset-3 z-40 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-beni/50 bg-ground/80 backdrop-blur-sm shadow-glow"
    >
      <FileUp className="h-6 w-6 text-beni-pale" />
      <p className="text-title text-paper-100">ここへ落として取り込む</p>
      <p className="text-label text-paper-400">
        <span className="font-mono text-paper-300">.irvm</span>
      </p>
    </m.div>
  );
}
