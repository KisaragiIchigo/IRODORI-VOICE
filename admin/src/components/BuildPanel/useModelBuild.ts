import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { messageOf } from "../../lib/errors";
import type { ModelParts } from "../../lib/model-parts";
import type { ModelBuildResult } from "../../lib/types";

/** 組み立ての段階。送り終えたあとエンジンが固める時間は、進捗が止まるため別の段にする。 */
export type BuildPhase =
  | { kind: "idle" }
  | { kind: "sending"; loaded: number; total: number }
  | { kind: "packing" };

export type BuildInput = {
  name: string;
  description: string;
  parts: ModelParts;
  /** 作ったあと、そのままライブラリへ入れるか。 */
  install: boolean;
};

type Options = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
  onChanged: () => void;
};

export function useModelBuild({ onNotify, onChanged }: Options) {
  const [phase, setPhase] = useState<BuildPhase>({ kind: "idle" });
  const [result, setResult] = useState<ModelBuildResult | null>(null);
  const [download, setDownload] = useState<string | null>(null);

  // 差し替えたときと画面を離れるときに、前の Blob を解放する。
  useEffect(() => {
    if (!download) return;
    return () => URL.revokeObjectURL(download);
  }, [download]);

  const build = useCallback(
    async ({ name, description, parts, install }: BuildInput) => {
      if (!parts.config || !parts.styleVectors) return;

      setPhase({ kind: "sending", loaded: 0, total: 0 });
      try {
        const form = new FormData();
        form.append("name", name);
        form.append("description", description);
        form.append("config", parts.config);
        form.append("style_vectors", parts.styleVectors);
        if (parts.model) form.append("model", parts.model);
        if (parts.onnx) form.append("onnx", parts.onnx);
        form.append("install", String(install));

        const { summary, blob } = await api.buildModel(form, {
          onProgress: (progress) => {
            setPhase(
              progress.total > 0 && progress.loaded >= progress.total
                ? { kind: "packing" }
                : { kind: "sending", loaded: progress.loaded, total: progress.total },
            );
          },
        });

        setResult(summary);
        setDownload(URL.createObjectURL(blob));
        onNotify(
          "success",
          summary.installed
            ? `${summary.name} を作成し、ライブラリへ取り込みました。`
            : `${summary.name} を作成しました。下のボタンから保存できます。`,
        );
        if (summary.installed) {
          onChanged();
        }
      } catch (cause) {
        onNotify("error", messageOf(cause, "作成に失敗しました。"));
      } finally {
        setPhase({ kind: "idle" });
      }
    },
    [onChanged, onNotify],
  );

  return { phase, busy: phase.kind !== "idle", result, download, build };
}
