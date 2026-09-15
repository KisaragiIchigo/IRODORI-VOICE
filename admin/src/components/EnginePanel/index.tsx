import { m } from "framer-motion";
import { AlertTriangle, Cpu, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";

import { useResource } from "../../hooks/useResource";
import { api, EngineError } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { BackendStatus, CheckpointList } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";

// MeanFlow 蒸留版は推論時の条件付けスケールを 0 に潰す。速度は上がるが、
// キャプションによる喋り分けと参照音声の寄せ具合が効かなくなる。
// 利用者が理由を知らずに選ぶと「スタイルを変えても同じ声」に見えるため明示する。
const MEANFLOW_ID = "Aratako/Irodori-TTS-v4.1-Small-MF";

type Props = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
};

export function EnginePanel({ onNotify }: Props) {
  const backends = useResource<BackendStatus[]>(api.listBackends, []);
  const models = useResource<CheckpointList | null>(
    useCallback(() => api.listCheckpoints(), []),
    null,
  );
  const [switching, setSwitching] = useState<string | null>(null);

  const select = async (checkpoint: string, steps: number | null) => {
    setSwitching(checkpoint);
    try {
      const result = await api.selectCheckpoint(checkpoint, steps ?? undefined);
      await models.reload();
      onNotify("success", result.detail);
    } catch (cause) {
      onNotify("error", cause instanceof EngineError ? cause.message : "切り替えに失敗しました。");
    } finally {
      setSwitching(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-paper-400" />
            <h2 className="text-label font-medium uppercase tracking-widest text-paper-300">
              エンジンの状態
            </h2>
          </div>
          <Button
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => void backends.reload()}
            busy={backends.loading}
          >
            再読み込み
          </Button>
        </CardHeader>
        <CardBody className="flex flex-col gap-2.5">
          {backends.error ? <p className="text-label text-beni-pale">{backends.error}</p> : null}
          {backends.data.map((backend) => (
            <div
              key={backend.backend_id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-white/[0.04] bg-black/20 px-3 py-2"
            >
              <span className="text-body font-medium text-paper-200">{backend.display_name}</span>
              <Badge tone={backend.available ? "success" : "warning"}>
                {backend.available ? "利用できます" : "利用できません"}
              </Badge>
              <span className="min-w-[18rem] flex-1 text-label text-paper-400">{backend.detail}</span>
              {backend.install_hint ? (
                <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-label text-paper-300">
                  {backend.install_hint}
                </code>
              ) : null}
            </div>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-label font-medium uppercase tracking-widest text-paper-300">
            合成モデル（チェックポイント）
          </h2>
          {models.data ? (
            <span className="font-mono text-label text-paper-400">
              サンプリング {models.data.current_steps ?? "モデル推奨"} 回
            </span>
          ) : null}
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {models.error ? <p className="text-label text-beni-pale">{models.error}</p> : null}
          {models.data?.checkpoints.map((entry) => {
            const isMeanflow = entry.checkpoint === MEANFLOW_ID;
            return (
              <m.button
                key={entry.checkpoint}
                type="button"
                whileHover={entry.selected ? undefined : { scale: 1.005 }}
                whileTap={entry.selected ? undefined : { scale: 0.995 }}
                disabled={entry.selected || switching !== null}
                onClick={() => void select(entry.checkpoint, entry.recommended_steps)}
                className={cn(
                  "flex flex-col gap-2 rounded-md border px-3.5 py-3 text-left transition-colors",
                  entry.selected
                    ? "border-beni/40 bg-beni/[0.07] shadow-glow"
                    : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]",
                  switching === entry.checkpoint && "animate-breathe",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-body font-medium text-paper-100">{entry.label}</span>
                  {entry.selected ? <Badge tone="accent">使用中</Badge> : null}
                  {!entry.downloaded ? <Badge tone="warning">未ダウンロード</Badge> : null}
                </div>
                <p className="text-label leading-relaxed text-paper-400">{entry.detail}</p>
                {isMeanflow ? (
                  <p className="flex items-start gap-1.5 text-label leading-relaxed text-shiracha">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      この版はキャプションによる喋り分け（よろこび・かなしみ・ささやき）と、
                      参照音声への寄せ具合が効きません。速度を最優先する場合にお選びください。
                    </span>
                  </p>
                ) : null}
                <code className="font-mono text-label text-paper-500">{entry.checkpoint}</code>
              </m.button>
            );
          })}
          <p className="text-label leading-relaxed text-paper-400">
            切り替えた設定は、エンジンを再起動すると反映されます。
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
