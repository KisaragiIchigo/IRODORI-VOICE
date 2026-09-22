import { NotebookPen } from "lucide-react";
import { useState } from "react";

import { Button } from "../ui/Button";

type Props = {
  memo: string;
  busy: boolean;
  /** 保存できたかを返す。失敗したときは書きかけを消さずに開いたままにする。 */
  onSave: (memo: string) => Promise<boolean>;
};

/** 話者へ後から書き添える覚え書き。合成には影響せず、この画面にだけ出る。 */
export function VoiceMemo({ memo, busy, onSave }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memo);
  const [saving, setSaving] = useState(false);

  const open = () => {
    setDraft(memo);
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    const saved = await onSave(draft.trim());
    setSaving(false);
    if (saved) setEditing(false);
  };

  if (!editing) {
    return (
      <div className="flex flex-wrap items-start gap-2">
        {memo ? (
          <p className="min-w-[16rem] flex-1 whitespace-pre-wrap rounded-md border border-white/[0.04] bg-black/20 px-2.5 py-2 text-label leading-relaxed text-paper-300">
            {memo}
          </p>
        ) : null}
        <Button
          className="shrink-0"
          icon={<NotebookPen className="h-3.5 w-3.5" />}
          onClick={open}
          disabled={busy}
        >
          {memo ? "メモを直す" : "メモを書く"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-white/[0.06] bg-black/20 p-2.5">
      <textarea
        autoFocus
        rows={3}
        value={draft}
        maxLength={1000}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setEditing(false);
        }}
        placeholder="どんな声か、どの動画で使ったか、シードをどこから拾ったかなど。"
        className="w-full resize-y rounded-md border border-white/[0.06] bg-black/40 px-3 py-2 text-body leading-relaxed text-paper-200 shadow-inset transition-colors placeholder:text-paper-500 focus:border-beni/50 focus:outline-none"
      />
      <div className="flex items-center justify-between gap-2">
        <p className="text-label text-paper-400">
          この画面にだけ表示されます。読み上げには影響しません。
        </p>
        <div className="flex shrink-0 items-center gap-2">
          <Button onClick={() => setEditing(false)} disabled={saving}>
            やめる
          </Button>
          <Button variant="primary" onClick={() => void save()} busy={saving} disabled={busy}>
            保存する
          </Button>
        </div>
      </div>
    </div>
  );
}
