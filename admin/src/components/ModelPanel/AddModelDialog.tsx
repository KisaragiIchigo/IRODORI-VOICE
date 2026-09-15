import * as Tabs from "@radix-ui/react-tabs";
import { m } from "framer-motion";
import { useState } from "react";

import { cn } from "../../lib/cn";
import { Modal } from "../ui/Modal";
import { Progress } from "../ui/Progress";
import { WorkingNote } from "../ui/WorkingNote";
import { FileDropZone } from "./FileDropZone";
import { FromFolderPath } from "./add/FromFolderPath";
import { FromFolderUpload } from "./add/FromFolderUpload";
import type { ImportPhase } from "./useModelImport";

const TABS = [
  { id: "file", label: "ファイルから" },
  { id: "upload", label: "フォルダを送る" },
  { id: "path", label: "フォルダを指す" },
] as const;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  phase: ImportPhase;
  busy: boolean;
  onFile: (file: File) => void;
  onUpload: (name: string, model: File, config: File, styleVectors: File) => void;
  onPath: (directory: string, name?: string) => void;
};

export function AddModelDialog({ open, onOpenChange, phase, busy, onFile, onUpload, onPath }: Props) {
  const [active, setActive] = useState<string>("file");

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="モデルを追加する"
      description="1 ファイルにまとまったモデルか、学習フォルダの中身から取り込めます。"
      dismissible={!busy}
    >
      <Tabs.Root value={active} onValueChange={setActive} className="flex flex-col">
        <Tabs.List className="flex gap-1 self-start px-5 pt-4">
          {TABS.map((tab) => (
            <Tabs.Trigger key={tab.id} value={tab.id} asChild>
              <button
                type="button"
                className={cn(
                  "relative rounded-md px-3 py-1.5 text-label font-medium tracking-wide transition-colors",
                  "text-paper-400 hover:text-paper-200 data-[state=active]:text-paper-100",
                )}
              >
                {active === tab.id ? (
                  <m.span
                    layoutId="add-model-tab"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    className="absolute inset-0 rounded-md border border-beni/30 bg-beni/[0.12]"
                  />
                ) : null}
                <span className="relative z-10">{tab.label}</span>
              </button>
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <div className="px-5 pb-5 pt-4">
          <Tabs.Content value="file" className="focus-visible:outline-none">
            <FileDropZone busy={busy} onPick={onFile} />
          </Tabs.Content>
          <Tabs.Content value="upload" className="focus-visible:outline-none">
            <FromFolderUpload busy={busy} onSubmit={onUpload} />
          </Tabs.Content>
          <Tabs.Content value="path" className="focus-visible:outline-none">
            <FromFolderPath busy={busy} onSubmit={onPath} />
          </Tabs.Content>
        </div>
      </Tabs.Root>

      {phase.kind === "idle" ? null : (
        <div className="border-t border-white/[0.06] bg-black/30 px-5 py-3.5">
          {phase.kind === "sending" ? (
            <Progress loaded={phase.loaded} total={phase.total} label={`送信中 ── ${phase.label}`} />
          ) : (
            <WorkingNote>エンジンが取り込んでいます ── {phase.label}</WorkingNote>
          )}
        </div>
      )}
    </Modal>
  );
}
