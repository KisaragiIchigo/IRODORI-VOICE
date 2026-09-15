import * as Tabs from "@radix-ui/react-tabs";
import { domAnimation, LazyMotion, m } from "framer-motion";
import { useCallback, useState } from "react";

import { EnginePanel } from "./components/EnginePanel";
import { BuildPanel } from "./components/BuildPanel";
import { ModelPanel } from "./components/ModelPanel";
import { ToastStack } from "./components/ui/Toast";
import { VoicePanel } from "./components/VoicePanel";
import { useResource } from "./hooks/useResource";
import { useToast } from "./hooks/useToast";
import { api } from "./lib/api";
import { cn } from "./lib/cn";
import type { Voice } from "./lib/types";

const TABS = [
  { id: "voices", label: "話者" },
  { id: "models", label: "音声モデル" },
  { id: "build", label: "モデルを作成" },
  { id: "engine", label: "エンジン" },
] as const;

export default function App() {
  const { toasts, push, dismiss } = useToast();
  const [active, setActive] = useState<string>("voices");
  const voices = useResource<Voice[]>(useCallback(() => api.listVoices(), []), []);
  // useResource が返すオブジェクト自体は毎回新しい。安定している reload だけを取り出す。
  const { reload: reloadVoiceList } = voices;
  const reloadVoices = useCallback(() => void reloadVoiceList(), [reloadVoiceList]);

  return (
    <LazyMotion features={domAnimation} strict>
      {/* エディタのダイアログの中で開くため、縦は画面いっぱいに固定して本文だけを流す。 */}
      <Tabs.Root
        value={active}
        onValueChange={setActive}
        className="flex h-screen flex-col overflow-hidden"
      >
        <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-white/[0.06] bg-black/25 px-4 py-2.5 backdrop-blur-md sm:px-6">
          <h1 className="font-display text-title font-semibold tracking-tight text-paper-100">
            IRODORI-VOICE
          </h1>

          <Tabs.List className="flex gap-1 rounded-lg border border-white/[0.06] bg-black/30 p-1">
            {TABS.map((tab) => (
              <Tabs.Trigger key={tab.id} value={tab.id} asChild>
                <button
                  type="button"
                  className={cn(
                    "relative rounded-md px-3.5 py-1.5 text-label font-medium tracking-wide transition-colors",
                    "text-paper-400 hover:text-paper-200",
                    "data-[state=active]:text-paper-100",
                  )}
                >
                  {/* 選択中の下地だけを描く。layoutId は同時に 1 つでないと滑らない。 */}
                  {active === tab.id ? (
                    <m.span
                      layoutId="tab-indicator"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                      className="absolute inset-0 rounded-md border border-beni/30 bg-beni/[0.12] shadow-glow"
                    />
                  ) : null}
                  <span className="relative z-10">{tab.label}</span>
                </button>
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          <p className="ml-auto text-label text-paper-400">
            読み上げの操作は VOICEVOX エディタで行います。この画面では素材の準備だけを行います。
          </p>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {/* 幅は各パネルが決める。一覧は広く、入力は読みやすい幅で止めたい。 */}
          <div className="px-4 py-5 sm:px-6">
            <Tabs.Content value="voices" className="focus-visible:outline-none">
              <VoicePanel
                voices={voices.data}
                loading={voices.loading}
                error={voices.error}
                reload={voices.reload}
                onNotify={push}
              />
            </Tabs.Content>

            <Tabs.Content value="models" className="focus-visible:outline-none">
              <ModelPanel onNotify={push} onChanged={reloadVoices} />
            </Tabs.Content>

            <Tabs.Content value="build" className="focus-visible:outline-none">
              <BuildPanel onNotify={push} onChanged={reloadVoices} />
            </Tabs.Content>

            <Tabs.Content value="engine" className="focus-visible:outline-none">
              <EnginePanel onNotify={push} />
            </Tabs.Content>
          </div>
        </div>
      </Tabs.Root>

      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </LazyMotion>
  );
}
