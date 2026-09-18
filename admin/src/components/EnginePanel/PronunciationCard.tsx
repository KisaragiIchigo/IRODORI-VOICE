import { m } from "framer-motion";
import { useCallback, useState } from "react";

import { useResource } from "../../hooks/useResource";
import { api, EngineError } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { EngineSettings, PronunciationMode } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Card, CardBody, CardHeader } from "../ui/Card";

type Choice = {
  mode: PronunciationMode;
  label: string;
  detail: string;
  example: string;
};

// Irodori-TTS は表記からそのまま音を作るため、読みへ置き換えた本文は
// 学習時と違う見た目になる。利用者が選ぶのは「読みの正しさ」と「抑揚の自然さ」の
// どちらを優先するかなので、例文で差が分かる形にする。
const CHOICES: Choice[] = [
  {
    mode: "off",
    label: "表記のまま読ませる",
    detail:
      "入力した文章をそのまま合成へ渡します。抑揚は Irodori-TTS 本体と同じ条件になり、"
      + "アクセントが最も自然になります。読み違えた語は、ユーザー辞書へ登録して直してください。",
    example: "設定画面から生成回数を変更できます。",
  },
  {
    mode: "kanji",
    label: "漢字の読みを明示する",
    detail:
      "漢字を含む語を、解析した読みへ置き換えてから合成へ渡します。難しい語や固有名詞の"
      + "読み違いは減りますが、語の切れ目の手がかりが消えるため、アクセントは崩れやすくなります。",
    example: "せっていがめんからせいせいかいすうをへんこうできます。",
  },
];

type Props = {
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
};

/** 漢字語の読みをモデルへ渡す前に置き換えるかどうかの切り替え。 */
export function PronunciationCard({ onNotify }: Props) {
  const settings = useResource<EngineSettings | null>(
    useCallback(() => api.readSettings(), []),
    null,
  );
  const [saving, setSaving] = useState<PronunciationMode | null>(null);

  const select = async (mode: PronunciationMode) => {
    setSaving(mode);
    try {
      await api.updateSettings({ pronunciation_mode: mode });
      await settings.reload();
      onNotify(
        "success",
        "読み方の指定を保存しました。合成済みの音は破棄したので、次の再生から変わります。",
      );
    } catch (cause) {
      onNotify("error", cause instanceof EngineError ? cause.message : "保存に失敗しました。");
    } finally {
      setSaving(null);
    }
  };

  const current = settings.data?.pronunciation_mode ?? null;

  return (
    <Card>
      <CardHeader>
        <h2 className="text-label font-medium uppercase tracking-widest text-paper-300">
          漢字の読み方
        </h2>
        <span className="text-label text-paper-400">Irodori 話者のみ</span>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        {settings.error ? <p className="text-label text-beni-pale">{settings.error}</p> : null}
        {CHOICES.map((choice) => {
          const selected = current === choice.mode;
          return (
            <m.button
              key={choice.mode}
              type="button"
              whileHover={selected ? undefined : { scale: 1.005 }}
              whileTap={selected ? undefined : { scale: 0.995 }}
              disabled={selected || saving !== null || current === null}
              onClick={() => void select(choice.mode)}
              className={cn(
                "flex flex-col gap-2 rounded-md border px-3.5 py-3 text-left transition-colors",
                selected
                  ? "border-beni/40 bg-beni/[0.07] shadow-glow"
                  : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]",
                saving === choice.mode && "animate-breathe",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-body font-medium text-paper-100">{choice.label}</span>
                {selected ? <Badge tone="accent">使用中</Badge> : null}
                {choice.mode === "off" ? <Badge>既定</Badge> : null}
              </div>
              <p className="text-body leading-relaxed text-paper-300">{choice.detail}</p>
              <p className="rounded bg-black/30 px-2 py-1.5 text-body text-paper-400">
                合成へ渡る文：{choice.example}
              </p>
            </m.button>
          );
        })}
        <p className="text-body leading-relaxed text-paper-400">
          この設定は参照音声から作った Irodori 話者に効きます。シード値で声を固定した話者と
          AIVM 話者は、どちらを選んでも表記のまま読み上げます。切り替えは保存した時点で
          反映され、エンジンの再起動は不要です。
        </p>
      </CardBody>
    </Card>
  );
}
