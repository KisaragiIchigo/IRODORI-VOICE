import { Check, Minus } from "lucide-react";

import { cn } from "../../../lib/cn";
import { formatSize } from "../../../lib/format";
import type { ModelParts, PartKey } from "../../../lib/model-parts";

type Row = { key: PartKey; label: string; pattern: string };

const ROWS: Row[] = [
  { key: "model", label: "学習済みモデル", pattern: "*.safetensors" },
  { key: "config", label: "ハイパーパラメータ", pattern: "config.json" },
  { key: "styleVectors", label: "スタイルベクトル", pattern: "style_vectors.npy" },
];

type Props = {
  parts: ModelParts;
};

/** 選んだフォルダに何が入っていたか。足りないものが一目で分かるようにする。 */
export function PartChecklist({ parts }: Props) {
  return (
    <ul className="flex flex-col gap-1">
      {ROWS.map((row) => {
        const file = parts[row.key];
        return (
          <li
            key={row.key}
            className={cn(
              "flex flex-wrap items-center gap-2.5 rounded-md border px-3 py-2",
              file
                ? "border-tokiwa-light/40 bg-tokiwa-light/[0.16]"
                : "border-shiracha/35 bg-shiracha/[0.10]",
            )}
          >
            {file ? (
              <Check className="h-3.5 w-3.5 shrink-0 text-tokiwa-pale" />
            ) : (
              <Minus className="h-3.5 w-3.5 shrink-0 text-shiracha" />
            )}
            <span className="w-36 shrink-0 text-label text-paper-200">{row.label}</span>
            <code className="shrink-0 font-mono text-label text-paper-400">{row.pattern}</code>
            <span
              className={cn(
                "min-w-[8rem] flex-1 truncate text-label",
                file ? "text-paper-400" : "text-shiracha",
              )}
            >
              {file ? `${file.name}（${formatSize(file.size)}）` : "見つかりません"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
