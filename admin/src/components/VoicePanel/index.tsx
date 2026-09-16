import * as Tabs from "@radix-ui/react-tabs";
import { m } from "framer-motion";
import { Mic2, RefreshCw, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "../../lib/api";
import { messageOf } from "../../lib/errors";
import type { CloneRequest, SeedVoiceRequest, Voice } from "../../lib/types";
import { cn } from "../../lib/cn";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { CloneForm } from "./CloneForm";
import { SeedForm } from "./SeedForm";
import { VoiceCard } from "./VoiceCard";

const MODES = [
  { id: "seed", label: "シードから" },
  { id: "clone", label: "声を借りる" },
] as const;

type Props = {
  voices: Voice[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
};

export function VoicePanel({ voices, loading, error, reload, onNotify }: Props) {
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<string>("seed");
  // アイコンの差し替えは URL を変えない。取り直させるために話者ごとの世代を持つ。
  const [iconVersions, setIconVersions] = useState<Record<string, number>>({});

  /** 声の手本にできる話者。Irodori-TTS の話者は手本にできないため除く。 */
  const sourceVoices = useMemo(
    () => voices.filter((voice) => voice.backend_id !== "irodori"),
    [voices],
  );

  const run = async (task: () => Promise<string>) => {
    setBusy(true);
    try {
      onNotify("success", await task());
      await reload();
    } catch (cause) {
      onNotify("error", messageOf(cause, "処理に失敗しました。"));
    } finally {
      setBusy(false);
    }
  };

  const clone = (payload: CloneRequest) =>
    void run(async () => {
      const created = await api.cloneFromModel(payload);
      return `${created.name} を作成しました。エディタの話者一覧に並びます。`;
    });

  const fromSeed = (payload: SeedVoiceRequest) =>
    void run(async () => {
      const created = await api.createVoiceFromSeed(payload);
      return `${created.name} を作成しました。エディタの話者一覧に並びます。`;
    });

  const markIconChanged = (voiceId: string) =>
    setIconVersions((current) => ({ ...current, [voiceId]: Date.now() }));

  const pickIcon = (voice: Voice, file: File) =>
    void run(async () => {
      await api.setVoiceIcon(voice.voice_id, file);
      markIconChanged(voice.voice_id);
      return `${voice.name} のアイコンを設定しました。`;
    });

  const clearIcon = (voice: Voice) =>
    void run(async () => {
      await api.clearVoiceIcon(voice.voice_id);
      markIconChanged(voice.voice_id);
      return `${voice.name} のアイコンを外しました。`;
    });

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <Card>
        <Tabs.Root value={mode} onValueChange={setMode}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-beni" />
              <h3 className="label-caps text-paper-300">話者を作る</h3>
            </div>
            <Tabs.List className="flex gap-1 rounded-lg border border-white/[0.06] bg-black/30 p-1">
              {MODES.map((entry) => (
                <Tabs.Trigger key={entry.id} value={entry.id} asChild>
                  <button
                    type="button"
                    className={cn(
                      "relative rounded-md px-3 py-1.5 text-label font-medium tracking-wide transition-colors",
                      "text-paper-400 hover:text-paper-200 data-[state=active]:text-paper-100",
                    )}
                  >
                    {mode === entry.id ? (
                      <m.span
                        layoutId="voice-mode-tab"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        className="absolute inset-0 rounded-md border border-beni/30 bg-beni/[0.12]"
                      />
                    ) : null}
                    <span className="relative z-10">{entry.label}</span>
                  </button>
                </Tabs.Trigger>
              ))}
            </Tabs.List>
          </CardHeader>

          <CardBody>
            <Tabs.Content value="clone" className="focus-visible:outline-none">
              <CloneForm
                sources={sourceVoices}
                busy={busy}
                onSubmit={clone}
                onSwitchToSeed={() => setMode("seed")}
              />
            </Tabs.Content>
            <Tabs.Content value="seed" className="focus-visible:outline-none">
              <SeedForm busy={busy} onSubmit={fromSeed} onNotify={onNotify} />
            </Tabs.Content>
          </CardBody>
        </Tabs.Root>
      </Card>

      <div className="flex items-center justify-between gap-3 pt-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <div className="flex items-center gap-2">
            <Mic2 className="h-4 w-4 text-paper-400" />
            <h2 className="label-caps text-paper-300">
              話者 {voices.length} 名
            </h2>
          </div>
          <p className="text-label text-paper-400">
            アイコンは枠をクリックするか、画像をドロップして設定できます。
            エディタの話者一覧には、この画面を閉じたときに反映されます。
          </p>
        </div>
        <Button
          icon={<RefreshCw className="h-3.5 w-3.5" />}
          onClick={() => void reload()}
          busy={loading}
        >
          再読み込み
        </Button>
      </div>

      {error ? (
        <p className="rounded-md border border-beni/35 bg-beni/[0.14] px-3 py-2 text-label text-beni-pale">
          {error}
        </p>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        {voices.map((voice) => (
          <VoiceCard
            key={voice.voice_id}
            voice={voice}
            busy={busy}
            iconVersion={iconVersions[voice.voice_id] ?? 0}
            onDelete={(voiceId) =>
              void run(async () => {
                await api.deleteVoice(voiceId);
                return `${voice.name} を削除しました。`;
              })
            }
            onPickIcon={(file) => pickIcon(voice, file)}
            onClearIcon={() => clearIcon(voice)}
            onBake={() =>
              void run(async () => {
                await api.bakeVoiceReference(voice.voice_id);
                return `${voice.name} の声を固定しました。どの行でも同じ声になります。`;
              })
            }
          />
        ))}
      </div>
    </div>
  );
}
