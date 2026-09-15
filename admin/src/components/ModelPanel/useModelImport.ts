import { useCallback, useState } from "react";

import { api } from "../../lib/api";
import { messageOf } from "../../lib/errors";
import type { UploadProgress } from "../../lib/upload";

/** 取り込みの段階。送り終えたあとの展開待ちは進捗が止まるため、別の段として持つ。 */
export type ImportPhase =
  | { kind: "idle" }
  | { kind: "sending"; label: string; loaded: number; total: number }
  | { kind: "working"; label: string };

type Options = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
  /** 取り込みが終わったとき。一覧と話者の取り直しに使う。 */
  onDone: () => void;
};

/** モデルを取り込む 3 つの経路を、同じ進捗と通知の上へ揃える。 */
export function useModelImport({ onNotify, onDone }: Options) {
  const [phase, setPhase] = useState<ImportPhase>({ kind: "idle" });

  const run = useCallback(
    async (label: string, task: (onProgress: (progress: UploadProgress) => void) => Promise<string>) => {
      setPhase({ kind: "sending", label, loaded: 0, total: 0 });
      try {
        const message = await task((progress) => {
          setPhase(
            progress.total > 0 && progress.loaded >= progress.total
              ? { kind: "working", label }
              : { kind: "sending", label, loaded: progress.loaded, total: progress.total },
          );
        });
        onNotify("success", message);
        onDone();
        return true;
      } catch (cause) {
        onNotify("error", messageOf(cause, "取り込みに失敗しました。"));
        return false;
      } finally {
        setPhase({ kind: "idle" });
      }
    },
    [onDone, onNotify],
  );

  /** 対応形式のモデルを 1 ファイル。 */
  const installFile = useCallback(
    (file: File) =>
      run(file.name, async (onProgress) => {
        const installed = await api.installModel(file, { onProgress });
        return installed.usable
          ? `${installed.name} を取り込みました。`
          : `${installed.name} を取り込みましたが、この形式では合成に使えません。`;
      }),
    [run],
  );

  /** フォルダの中身を送って取り込む。 */
  const installUpload = useCallback(
    (name: string, model: File, config: File, styleVectors: File) =>
      run(`${name}（${model.name}）`, async (onProgress) => {
        const installed = await api.installSbv2(name, model, config, styleVectors, { onProgress });
        return `${installed.name} を取り込みました。`;
      }),
    [run],
  );

  /** フォルダの場所を渡し、エンジンに直接読ませる。送信が無いぶん速い。 */
  const installFromPath = useCallback(
    (directory: string, name?: string) =>
      run(directory, async () => {
        const built = await api.buildFromFolder(directory, name);
        return `${built.name} を取り込みました。`;
      }),
    [run],
  );

  return {
    phase,
    busy: phase.kind !== "idle",
    installFile,
    installUpload,
    installFromPath,
  };
}
