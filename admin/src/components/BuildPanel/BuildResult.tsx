import { Download } from "lucide-react";

import { formatSize } from "../../lib/format";
import type { ModelBuildResult } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Card, CardBody, CardHeader } from "../ui/Card";

type Props = {
  result: ModelBuildResult;
  /** 作った直後だけ保存できる。取り直しはできないので、リンクが無いときは出さない。 */
  download: string | null;
};

export function BuildResult({ result, download }: Props) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="label-caps text-paper-300">できたモデル</h3>
          {result.installed ? (
            <Badge tone="success">取り込み済み</Badge>
          ) : (
            <Badge tone="neutral">ファイルのみ</Badge>
          )}
        </div>
        {download ? (
          <a
            href={download}
            download={result.file_name}
            className="inline-flex shrink-0 items-center gap-2 rounded-md border border-beni/30 bg-beni/[0.12] px-3 py-1.5 text-label font-medium text-beni-pale shadow-glow transition-colors hover:bg-beni/[0.18]"
          >
            <Download className="h-3.5 w-3.5" />
            保存する
          </a>
        ) : null}
      </CardHeader>
      <CardBody>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-label">
          <dt className="text-paper-400">名前</dt>
          <dd className="text-paper-200">{result.name}</dd>
          <dt className="text-paper-400">構造</dt>
          <dd className="font-mono text-paper-300">{result.model_architecture}</dd>
          <dt className="text-paper-400">同梱</dt>
          <dd className="flex flex-wrap gap-1.5">
            {result.has_safetensors ? <Badge tone="success">Safetensors</Badge> : null}
            {result.has_onnx ? <Badge tone="neutral">ONNX</Badge> : null}
          </dd>
          <dt className="text-paper-400">話者</dt>
          <dd className="text-paper-300">
            {result.speaker_count} 名 ／ スタイル {result.style_count} 種
          </dd>
          <dt className="text-paper-400">大きさ</dt>
          <dd className="font-mono text-paper-300">{formatSize(result.size_bytes)}</dd>
        </dl>
      </CardBody>
    </Card>
  );
}
