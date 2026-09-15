import { Boxes, Plus, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";

import { useResource } from "../../hooks/useResource";
import { api } from "../../lib/api";
import { messageOf } from "../../lib/errors";
import type { InstalledModel } from "../../lib/types";
import { Button } from "../ui/Button";
import { Progress } from "../ui/Progress";
import { WorkingNote } from "../ui/WorkingNote";
import { AddModelDialog } from "./AddModelDialog";
import { AddTile } from "./AddTile";
import { DropOverlay } from "./DropOverlay";
import { EmptyState } from "./EmptyState";
import { ModelCard } from "./ModelCard";
import { useModelImport } from "./useModelImport";

type Props = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
  /** 話者一覧にも影響するため、取り込み後に親へ知らせる。 */
  onChanged: () => void;
};

export function ModelPanel({ onNotify, onChanged }: Props) {
  const models = useResource<InstalledModel[]>(useCallback(() => api.listModels(), []), []);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  // useResource が返すオブジェクトは毎回新しい。安定している reload だけを取り出す。
  const { reload: reloadModels } = models;
  const refresh = useCallback(() => {
    void reloadModels();
    onChanged();
  }, [onChanged, reloadModels]);

  const importer = useModelImport({ onNotify, onDone: refresh });

  // 取り込めたときだけ閉じる。失敗したら、直して押し直せるよう開いたままにする。
  const closeIfDone = async (done: Promise<boolean>) => {
    if (await done) {
      setAdding(false);
    }
  };

  const remove = async (model: InstalledModel) => {
    setRemoving(model.uuid);
    try {
      await api.deleteModel(model.uuid);
      onNotify("success", `${model.name} を削除しました。`);
      refresh();
    } catch (cause) {
      onNotify("error", messageOf(cause, "削除に失敗しました。"));
    } finally {
      setRemoving(null);
    }
  };

  const empty = models.data.length === 0 && !models.loading;

  return (
    <div className="mx-auto flex w-full max-w-[92rem] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Boxes className="h-4 w-4 text-paper-400" />
          <h2 className="label-caps text-paper-300">
            取り込み済みのモデル {models.data.length} 件
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Button
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => void reloadModels()}
            busy={models.loading}
          >
            再読み込み
          </Button>
          <Button
            variant="primary"
            icon={<Plus className="h-3.5 w-3.5" />}
            onClick={() => setAdding(true)}
            disabled={importer.busy}
          >
            モデルを追加
          </Button>
        </div>
      </div>

      {models.error ? (
        <p className="rounded-md border border-beni/35 bg-beni/[0.14] px-3 py-2 text-label text-beni-pale">
          {models.error}
        </p>
      ) : null}

      {/* 画面へ直接落とされたときの進み具合。モーダルを開いている間は、そちらへ出す。 */}
      {!adding && importer.phase.kind === "sending" ? (
        <Progress
          loaded={importer.phase.loaded}
          total={importer.phase.total}
          label={`送信中 ── ${importer.phase.label}`}
        />
      ) : null}
      {!adding && importer.phase.kind === "working" ? (
        <WorkingNote>エンジンが取り込んでいます ── {importer.phase.label}</WorkingNote>
      ) : null}

      {empty ? (
        <EmptyState
          busy={importer.busy}
          onPick={(file) => void importer.installFile(file)}
          onOpenAdd={() => setAdding(true)}
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {models.data.map((model) => (
            <ModelCard
              key={model.uuid}
              model={model}
              busy={removing === model.uuid}
              onDelete={() => void remove(model)}
            />
          ))}
          <AddTile onClick={() => setAdding(true)} disabled={importer.busy} />
        </div>
      )}

      <AddModelDialog
        open={adding}
        onOpenChange={setAdding}
        phase={importer.phase}
        busy={importer.busy}
        onFile={(file) => void closeIfDone(importer.installFile(file))}
        onUpload={(name, model, config, styleVectors) =>
          void closeIfDone(importer.installUpload(name, model, config, styleVectors))
        }
        onPath={(directory, name) => void closeIfDone(importer.installFromPath(directory, name))}
      />

      <DropOverlay onDrop={(file) => void importer.installFile(file)} disabled={importer.busy} />
    </div>
  );
}
