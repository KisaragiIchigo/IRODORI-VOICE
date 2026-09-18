import { BackendStatusCard } from "./BackendStatusCard";
import { CheckpointCard } from "./CheckpointCard";
import { PronunciationCard } from "./PronunciationCard";

type Props = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
};

/** エンジンの状態と、合成条件の設定をまとめた画面。 */
export function EnginePanel({ onNotify }: Props) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <BackendStatusCard />
      <CheckpointCard onNotify={onNotify} />
      <PronunciationCard onNotify={onNotify} />
    </div>
  );
}
