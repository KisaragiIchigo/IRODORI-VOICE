import { Cpu, RefreshCw } from "lucide-react";

import { useResource } from "../../hooks/useResource";
import { api } from "../../lib/api";
import type { BackendStatus } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";

/** 合成に使えるバックエンドと、使えない場合の理由を並べる。 */
export function BackendStatusCard() {
  const backends = useResource<BackendStatus[]>(api.listBackends, []);

  return (
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
  );
}
