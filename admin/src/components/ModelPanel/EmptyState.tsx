import { FileDropZone } from "./FileDropZone";

type Props = {
  busy: boolean;
  onPick: (file: File) => void;
  /** フォルダから取り込みたい人のための逃げ道。 */
  onOpenAdd: () => void;
};

/** まだ 1 つも無いときの画面。最初の 1 つを置く場所を主役にする。 */
export function EmptyState({ busy, onPick, onOpenAdd }: Props) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
      <FileDropZone busy={busy} onPick={onPick} size="hero" />
      <p className="text-center text-label leading-relaxed text-paper-400">
        ばらばらのファイル（<code className="font-mono text-paper-300">*.safetensors</code> と{" "}
        <code className="font-mono text-paper-300">config.json</code> と{" "}
        <code className="font-mono text-paper-300">style_vectors.npy</code>）しか無い場合は、
        <button
          type="button"
          onClick={onOpenAdd}
          className="mx-1 rounded px-1 text-beni-pale underline decoration-beni/40 underline-offset-2 transition-colors hover:decoration-beni"
        >
          フォルダから取り込む
        </button>
        を使ってください。
      </p>
    </div>
  );
}
