import { AlertTriangle, ChevronDown, Trash2, Users } from "lucide-react";
import { useState } from "react";

import { cn } from "../../lib/cn";
import type { InstalledModel } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";

type Props = {
  model: InstalledModel;
  busy: boolean;
  onDelete: (uuid: string) => void;
};

export function ModelCard({ model, busy, onDelete }: Props) {
  // 削除は取り消せないので二段構えにする。確認ダイアログを重ねるより視線が動かない。
  const [confirming, setConfirming] = useState(false);
  // 出どころとライセンスは、必要になったときだけ開く。一覧では話者が見えていればいい。
  const [expanded, setExpanded] = useState(false);

  const hasDetail = model.creators.length > 0 || Boolean(model.license);

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate text-body font-medium text-paper-100">{model.name}</span>
          <Badge tone={model.usable ? "neutral" : "warning"}>{model.model_format}</Badge>
          {model.usable ? null : <Badge tone="warning">合成には使えません</Badge>}
        </div>
        {confirming ? (
          <div className="flex shrink-0 items-center gap-2">
            <span className="text-label text-beni-pale">削除しますか？</span>
            <Button variant="danger" busy={busy} onClick={() => onDelete(model.uuid)}>
              はい
            </Button>
            <Button onClick={() => setConfirming(false)}>やめる</Button>
          </div>
        ) : (
          <Button
            icon={<Trash2 className="h-3.5 w-3.5" />}
            onClick={() => setConfirming(true)}
            disabled={busy}
            aria-label={`${model.name} を削除`}
          />
        )}
      </CardHeader>

      <CardBody className="flex flex-1 flex-col gap-2.5 py-3">
        {model.description ? (
          <p className="line-clamp-2 text-label leading-relaxed text-paper-400">
            {model.description}
          </p>
        ) : null}

        {model.note ? (
          <p className="flex items-start gap-1.5 rounded-md border border-shiracha/35 bg-shiracha/[0.10] px-2.5 py-2 text-label leading-relaxed text-shiracha">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{model.note}</span>
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <span className="label-caps flex shrink-0 items-center gap-1.5">
            <Users className="h-3.5 w-3.5" />
            話者 {model.speakers.length} 名
          </span>
          {model.speakers.map((speaker) => (
            <Badge key={speaker.uuid} tone="neutral">
              {speaker.name}
              <span className="text-paper-400">／{speaker.styles.length} スタイル</span>
            </Badge>
          ))}
        </div>

        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/[0.04] pt-2 text-label text-paper-400">
          <span className="flex items-center gap-1.5">
            <span className="text-paper-400">構造</span>
            <span className="font-mono text-paper-300">{model.model_architecture}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-paper-400">版</span>
            <span className="font-mono text-paper-300">{model.version}</span>
          </span>
          {hasDetail ? (
            <button
              type="button"
              onClick={() => setExpanded((current) => !current)}
              className="ml-auto flex items-center gap-1 rounded px-1 py-0.5 text-label text-paper-400 transition-colors hover:text-paper-200"
            >
              出どころ
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")}
              />
            </button>
          ) : null}
        </div>

        {expanded && hasDetail ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-label text-paper-400">
            {model.creators.length > 0 ? (
              <>
                <dt className="text-paper-400">制作</dt>
                <dd>{model.creators.join("、")}</dd>
              </>
            ) : null}
            {model.license ? (
              <>
                <dt className="text-paper-400">ライセンス</dt>
                <dd className="max-h-40 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                  {model.license}
                </dd>
              </>
            ) : null}
          </dl>
        ) : null}
      </CardBody>
    </Card>
  );
}
