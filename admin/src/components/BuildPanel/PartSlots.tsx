import { Check, FolderOpen, Minus } from "lucide-react";
import { useRef } from "react";

import { cn } from "../../lib/cn";
import { formatSize } from "../../lib/format";
import type { ModelParts, PartKey } from "../../lib/model-parts";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

type Slot = {
  key: PartKey;
  label: string;
  pattern: string;
  accept: string;
  required: boolean;
};

const SLOTS: Slot[] = [
  { key: "model", label: "学習済みモデル", pattern: "*.safetensors", accept: ".safetensors,.pth", required: false },
  { key: "onnx", label: "ONNX モデル", pattern: "*.onnx", accept: ".onnx", required: false },
  { key: "config", label: "ハイパーパラメータ", pattern: "config.json", accept: ".json", required: true },
  { key: "styleVectors", label: "スタイルベクトル", pattern: "style_vectors.npy", accept: ".npy", required: true },
];

type Props = {
  parts: ModelParts;
  busy: boolean;
  onPickFolder: (files: File[]) => void;
  onPickOne: (key: PartKey, file: File) => void;
  onClear: (key: PartKey) => void;
};

/** 4 つの材料の受け口。フォルダから一括で拾うか、1 つずつ差し替える。 */
export function PartSlots({ parts, busy, onPickFolder, onPickOne, onClear }: Props) {
  const folderRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          icon={<FolderOpen className="h-3.5 w-3.5" />}
          onClick={() => folderRef.current?.click()}
          disabled={busy}
        >
          フォルダから一括で拾う
        </Button>
        <span className="text-label text-paper-400">
          下の行をクリックすると 1 つずつ選び直せます。
        </span>
      </div>

      <div className="grid gap-1.5">
        {SLOTS.map((slot) => {
          const file = parts[slot.key];
          return (
            <label
              key={slot.key}
              className={cn(
                "flex cursor-pointer flex-wrap items-center gap-2.5 rounded-md border px-3 py-2 transition-colors",
                file
                  ? "border-tokiwa-light/40 bg-tokiwa-light/[0.16] hover:bg-tokiwa-light/[0.24]"
                  : slot.required
                    ? "border-shiracha/35 bg-shiracha/[0.09] hover:bg-shiracha/[0.15]"
                    : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]",
              )}
            >
              {file ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-tokiwa-pale" />
              ) : (
                <Minus
                  className={cn(
                    "h-3.5 w-3.5 shrink-0",
                    slot.required ? "text-shiracha" : "text-paper-400",
                  )}
                />
              )}
              <span className="w-36 shrink-0 text-label text-paper-200">{slot.label}</span>
              <code className="shrink-0 font-mono text-label text-paper-400">{slot.pattern}</code>
              {slot.required ? <Badge tone="warning">必須</Badge> : <Badge tone="neutral">任意</Badge>}
              <span className="min-w-[8rem] flex-1 truncate text-label text-paper-400">
                {file ? `${file.name}（${formatSize(file.size)}）` : "未選択"}
              </span>
              {file ? (
                <button
                  type="button"
                  onClick={(event) => {
                    // ラベルの中なので、押すとファイル選択が開いてしまう。
                    event.preventDefault();
                    onClear(slot.key);
                  }}
                  className="shrink-0 rounded px-1.5 py-0.5 text-label text-paper-400 transition-colors hover:text-beni-pale"
                >
                  外す
                </button>
              ) : null}
              <input
                type="file"
                accept={slot.accept}
                className="hidden"
                disabled={busy}
                onChange={(event) => {
                  const chosen = event.target.files?.[0];
                  if (chosen) onPickOne(slot.key, chosen);
                  event.target.value = "";
                }}
              />
            </label>
          );
        })}
      </div>

      <input
        ref={folderRef}
        type="file"
        multiple
        webkitdirectory=""
        className="hidden"
        onChange={(event) => {
          onPickFolder(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
    </div>
  );
}
