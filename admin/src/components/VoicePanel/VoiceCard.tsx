import { Trash2 } from "lucide-react";
import { useState } from "react";

import type { Voice } from "../../lib/types";
import { VOICE_COLOR_HEX } from "../../lib/types";
import { Badge, ColorDot } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { VoiceIcon } from "./VoiceIcon";

type Props = {
  voice: Voice;
  busy: boolean;
  /** アイコンの世代。差し替えた直後に取り直させるために親が進める。 */
  iconVersion: number;
  onDelete: (voiceId: string) => void;
  onPickIcon: (file: File) => void;
  onClearIcon: () => void;
};

export function VoiceCard({
  voice,
  busy,
  iconVersion,
  onDelete,
  onPickIcon,
  onClearIcon,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const hex = VOICE_COLOR_HEX[voice.color_key] ?? VOICE_COLOR_HEX.shu;

  return (
    <Card>
      <CardHeader>
        <div className="flex min-w-0 items-center gap-2">
          <ColorDot hex={hex} />
          <span className="truncate text-body font-medium text-paper-100">{voice.name}</span>
          <Badge tone={voice.backend_id === "irodori" ? "accent" : "neutral"}>
            {voice.backend_id === "irodori" ? "Irodori-TTS" : "モデル"}
          </Badge>
          {voice.is_builtin ? <Badge tone="neutral">同梱</Badge> : null}
        </div>
        {voice.is_builtin ? null : confirming ? (
          <div className="flex shrink-0 items-center gap-2">
            <span className="text-label text-beni-pale">削除しますか？</span>
            <Button variant="danger" busy={busy} onClick={() => onDelete(voice.voice_id)}>
              はい
            </Button>
            <Button onClick={() => setConfirming(false)}>やめる</Button>
          </div>
        ) : (
          <Button
            icon={<Trash2 className="h-3.5 w-3.5" />}
            onClick={() => setConfirming(true)}
            disabled={busy || voice.backend_id === "aivm"}
          >
            削除
          </Button>
        )}
      </CardHeader>
      <CardBody className="flex gap-3">
        <VoiceIcon
          voice={voice}
          version={iconVersion}
          busy={busy}
          onPick={onPickIcon}
          onClear={onClearIcon}
        />

        <div className="flex min-w-0 flex-1 flex-col gap-2.5">
          {voice.description ? (
            <p className="text-label leading-relaxed text-paper-400">{voice.description}</p>
          ) : null}

          <div className="flex flex-wrap gap-1.5">
            {voice.styles.map((style) => (
              <Badge key={style.style_id} tone="neutral">
                {style.emoji ? <span aria-hidden>{style.emoji}</span> : null}
                {style.name}
              </Badge>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {voice.has_reference ? <Badge tone="success">参照音声で作成</Badge> : null}
            {voice.capabilities.emoji_style ? <Badge tone="neutral">絵文字で表情</Badge> : null}
            {voice.capabilities.pitch ? <Badge tone="neutral">音高調整</Badge> : null}
            {voice.capabilities.intonation ? <Badge tone="neutral">抑揚調整</Badge> : null}
            <Badge tone="neutral">
              <span className="font-mono">{(voice.sample_rate / 1000).toFixed(1)}kHz</span>
            </Badge>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
