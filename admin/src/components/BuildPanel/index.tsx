import * as Switch from "@radix-ui/react-switch";
import { Package } from "lucide-react";
import { useState } from "react";

import { cn } from "../../lib/cn";
import { formatSize } from "../../lib/format";
import type { ModelParts, PartKey } from "../../lib/model-parts";
import { folderNameOf, pickParts, totalSizeOf } from "../../lib/model-parts";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { TextField } from "../ui/Field";
import { Progress } from "../ui/Progress";
import { WorkingNote } from "../ui/WorkingNote";
import { BuildResult } from "./BuildResult";
import { PartSlots } from "./PartSlots";
import { Section } from "./Section";
import { useModelBuild } from "./useModelBuild";

type Props = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
  onChanged: () => void;
};

/** 足りないものを、そのまま読める言葉で返す。 */
function missingOf(parts: ModelParts): string[] {
  const missing: string[] = [];
  if (!parts.config) missing.push("config.json");
  if (!parts.styleVectors) missing.push("style_vectors.npy");
  if (!parts.model && !parts.onnx) missing.push("*.safetensors か *.onnx");
  return missing;
}

export function BuildPanel({ onNotify, onChanged }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [parts, setParts] = useState<ModelParts>({});
  const [install, setInstall] = useState(true);
  const builder = useModelBuild({ onNotify, onChanged });

  const missing = missingOf(parts);
  const total = totalSizeOf(parts);
  const ready = missing.length === 0 && Boolean(name.trim());

  const clear = (key: PartKey) => setParts((current) => ({ ...current, [key]: undefined }));

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-beni" />
            <h3 className="label-caps text-paper-300">モデルを作成する</h3>
          </div>
          <Badge tone="accent">
            <span className="font-mono">.irvm</span>
          </Badge>
        </CardHeader>

        <CardBody className="flex flex-col gap-5">
          <p className="text-label leading-relaxed text-paper-400">
            ばらばらに配布された材料を 1 つのファイルへまとめます。以後はこの 1 ファイルを渡すだけで
            取り込めるようになります。
          </p>

          <Section
            step={1}
            title="材料をそろえる"
            aside={
              total > 0 ? (
                <span className="shrink-0 text-label text-paper-400">
                  合計 <span className="font-mono text-paper-300">{formatSize(total)}</span>
                </span>
              ) : null
            }
          >
            <PartSlots
              parts={parts}
              busy={builder.busy}
              onPickFolder={(files) => {
                setParts(pickParts(files));
                // フォルダ名がそのまま名前になることが多い。書き換えたものは残す。
                setName((current) => current || folderNameOf(files));
              }}
              onPickOne={(key, file) => setParts((current) => ({ ...current, [key]: file }))}
              onClear={clear}
            />
          </Section>

          <Section step={2} title="名前をつける">
            <div className="grid gap-3 md:grid-cols-2">
              <TextField
                label="モデルの名前"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例: 〇〇ボイス"
                hint="話者一覧とファイル名に使われます。"
              />
              <TextField
                label="説明（任意）"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="配布元や用途など"
              />
            </div>
          </Section>

          <Section step={3} title="まとめる">
            <label className="flex items-start gap-3 rounded-md border border-white/[0.04] bg-black/20 px-3 py-2.5">
              <Switch.Root
                checked={install}
                onCheckedChange={setInstall}
                className={cn(
                  "relative mt-0.5 h-5 w-9 shrink-0 rounded-full border transition-colors",
                  install
                    ? "border-beni/40 bg-beni/30 shadow-glow"
                    : "border-white/[0.08] bg-white/[0.04]",
                )}
              >
                <Switch.Thumb
                  className={cn(
                    "block h-3.5 w-3.5 rounded-full bg-paper-200 transition-transform",
                    "translate-x-1 data-[state=checked]:translate-x-[1.15rem]",
                  )}
                />
              </Switch.Root>
              <span className="flex flex-col gap-0.5">
                <span className="text-body text-paper-200">作ったあと、そのまま取り込む</span>
                <span className="text-label leading-relaxed text-paper-400">
                  切っておくと、ファイルを受け取るだけになります。配布用に作る場合はこちらです。
                </span>
              </span>
            </label>

            {ready ? null : (
              <p className="rounded-md border border-shiracha/35 bg-shiracha/[0.09] px-3 py-2 text-label leading-relaxed text-shiracha">
                {missing.length > 0
                  ? `あと ${missing.join("、")} が必要です。`
                  : "モデルの名前を入れてください。"}
              </p>
            )}

            <Button
              variant="primary"
              className="self-start px-4 py-2"
              disabled={!ready}
              busy={builder.busy}
              onClick={() => void builder.build({ name: name.trim(), description: description.trim(), parts, install })}
            >
              この材料でモデルを作る
            </Button>

            {builder.phase.kind === "sending" ? (
              <Progress
                loaded={builder.phase.loaded}
                total={builder.phase.total}
                label="材料をエンジンへ送っています"
              />
            ) : null}
            {builder.phase.kind === "packing" ? (
              <WorkingNote>エンジンが 1 つのファイルへまとめています</WorkingNote>
            ) : null}
          </Section>
        </CardBody>
      </Card>

      {builder.result ? (
        <BuildResult result={builder.result} download={builder.download} />
      ) : null}
    </div>
  );
}
