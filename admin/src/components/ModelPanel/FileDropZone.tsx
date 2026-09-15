import { m } from "framer-motion";
import { FileUp } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "../../lib/cn";

// 案内文で名前を出すのは .irvm だけだが、受け入れ自体は 3 種のまま残す。
const ACCEPTED = [".aivm", ".aivmx", ".irvm"];

type Props = {
  busy: boolean;
  onPick: (file: File) => void;
  /** 一覧が空のときは、画面の主役として大きく出す。 */
  size?: "compact" | "hero";
};

/** モデル 1 ファイルを受け取る枠。ドロップとクリックのどちらでも開ける。 */
export function FileDropZone({ busy, onPick, size = "compact" }: Props) {
  const [hovering, setHovering] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      onPick(file);
    }
  };

  return (
    <m.div
      onDragOver={(event) => {
        event.preventDefault();
        setHovering(true);
      }}
      onDragLeave={() => setHovering(false)}
      onDrop={(event) => {
        event.preventDefault();
        setHovering(false);
        accept(event.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      whileHover={busy ? undefined : { scale: 1.004 }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed",
        "text-center transition-colors",
        size === "hero" ? "px-6 py-12" : "px-4 py-8",
        hovering
          ? "border-beni/50 bg-beni/[0.06] shadow-glow"
          : "border-white/[0.1] bg-black/20 hover:bg-white/[0.03]",
        busy && "pointer-events-none animate-breathe opacity-60",
      )}
    >
      <FileUp className={cn("text-paper-400", size === "hero" ? "h-5 w-5" : "h-4 w-4")} />
      <p className={cn("text-paper-200", size === "hero" ? "text-title" : "text-body")}>
        {busy ? "取り込んでいます…" : "モデルのファイルをここへドロップ"}
      </p>
      <p className="max-w-xl text-label leading-relaxed text-paper-400">
        {busy ? (
          "送り終わるまで、このまま置いておいてください。"
        ) : (
          <>
            クリックして選ぶこともできます。
            <span className="font-mono text-paper-300">.irvm</span> に対応しています。1
            つのファイルにモデル本体・設定・スタイルベクトルがまとまっているため、この形式が
            もっとも手軽です。
          </>
        )}
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        className="hidden"
        onChange={(event) => {
          accept(event.target.files);
          // 同じファイルを選び直したときにも change が起きるようにする。
          event.target.value = "";
        }}
      />
    </m.div>
  );
}
