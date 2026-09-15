import * as Switch from "@radix-ui/react-switch";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "../../lib/cn";
import type { CloneRequest, Voice } from "../../lib/types";
import { Button } from "../ui/Button";
import { SelectField, TextAreaField, TextField } from "../ui/Field";
import { CaptionField } from "./CaptionField";
import { ColorPicker } from "./ColorPicker";

type Props = {
  /** 合成に使える手本の話者。合成できない形式はエンジン側で除かれている。 */
  sources: Voice[];
  busy: boolean;
  onSubmit: (payload: CloneRequest) => void;
  /** 元になる声が無いときの逃げ道。 */
  onSwitchToSeed: () => void;
};

export function CloneForm({ sources, busy, onSubmit, onSwitchToSeed }: Props) {
  const [sourceId, setSourceId] = useState("");
  const [styleId, setStyleId] = useState("");
  const [name, setName] = useState("");
  const [colorKey, setColorKey] = useState<string>("wakatake");
  const [withEmotion, setWithEmotion] = useState(true);
  const [caption, setCaption] = useState("");
  const [customLines, setCustomLines] = useState("");
  const [showLines, setShowLines] = useState(false);

  const selected = useMemo(
    () => sources.find((voice) => voice.voice_id === sourceId),
    [sources, sourceId],
  );

  const submit = () => {
    const lines = customLines
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    onSubmit({
      source_voice_id: sourceId,
      source_style_id: styleId || null,
      name: name.trim(),
      color_key: colorKey,
      description: selected ? `${selected.name} の声を参照した話者` : "",
      with_emotion_styles: withEmotion,
      reference_lines: lines.length > 0 ? lines : null,
      caption: caption.trim() || null,
    });
  };

  if (sources.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-body leading-relaxed text-paper-400">
          元になる音声モデルがありません。「音声モデル」タブから取り込むと、
          その声を使えるようになります。合成に使えない形式は、ここには並びません。
        </p>
        <p className="text-body leading-relaxed text-paper-400">
          モデルを用意せずに話者を作りたい場合は、
          <button
            type="button"
            onClick={onSwitchToSeed}
            className="mx-1 rounded px-1 text-beni-pale underline decoration-beni/40 underline-offset-2 transition-colors hover:decoration-beni"
          >
            シードから作る
          </button>
          を使ってください。声はシード値だけで決まります。
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-label leading-relaxed text-paper-400">
        選んだ音声モデルで参照用の音声を合成し、それを手本にして Irodori-TTS の話者を作ります。
        声はモデルから、抑揚と間の取り方は Irodori-TTS から受け継ぎます。作成には十数秒かかります。
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        <SelectField
          label="元にする声"
          value={sourceId}
          onChange={(event) => {
            setSourceId(event.target.value);
            setStyleId("");
          }}
        >
          <option value="">選択してください</option>
          {sources.map((voice) => (
            <option key={voice.voice_id} value={voice.voice_id}>
              {voice.name}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="元の声のスタイル"
          value={styleId}
          onChange={(event) => setStyleId(event.target.value)}
          disabled={!selected}
        >
          <option value="">既定（先頭のスタイル）</option>
          {selected?.styles.map((style) => (
            <option key={style.style_id} value={style.style_id}>
              {style.name}
            </option>
          ))}
        </SelectField>
      </div>

      <TextField
        label="新しい話者の名前"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="例: 〇〇（写し）"
        hint="エディタの話者一覧にこの名前で並びます。"
      />

      <ColorPicker value={colorKey} onChange={setColorKey} />

      <CaptionField
        value={caption}
        onChange={setCaption}
        hint="ノーマルのスタイルにだけ入る話し方の指定です。喜怒哀楽のスタイルは、それぞれ固有の指示を持っているため変わりません。声そのものは参照した音声で決まるため、ここで変えられるのは話し方だけです。"
      />

      <label className="flex items-start gap-3 rounded-md border border-white/[0.04] bg-black/20 px-3 py-2.5">
        <Switch.Root
          checked={withEmotion}
          onCheckedChange={setWithEmotion}
          className={cn(
            "relative mt-0.5 h-5 w-9 shrink-0 rounded-full border transition-colors",
            withEmotion
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
          <span className="text-body text-paper-200">喜怒哀楽のスタイルも作る</span>
          <span className="text-label leading-relaxed text-paper-400">
            あかるい・よろこび・やさしさ・あんど・じしん・からかい・かんがえ・かんたん・おどろき・
            てれ・ふあん・あせり・くるしげ・おこり・あきれ・ねむそう・よい・ちからづよく・おねがい・
            ろうどく・かなしみ・まじめ・ゆっくり・はやくちの 24 種類を追加します。
            同じ声のまま口調を変えられます。なお、この喋り分けは標準チェックポイントでのみ効きます。
          </span>
        </span>
      </label>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setShowLines((value) => !value)}
          className="flex items-center gap-1.5 self-start text-label text-paper-400 transition-colors hover:text-paper-200"
        >
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", showLines && "rotate-180")}
          />
          参照文を自分で決める（任意）
        </button>
        {showLines ? (
          <TextAreaField
            label="参照文"
            rows={5}
            value={customLines}
            onChange={(event) => setCustomLines(event.target.value)}
            placeholder={"1 行に 1 文ずつ書きます。\n空欄のままにすると、既定の 4 文を使います。"}
            hint="合計 30 秒を超えた分は使われません。声の癖が出やすい文を選ぶと精度が上がります。"
          />
        ) : null}
      </div>

      <Button
        variant="primary"
        className="self-start px-4 py-2"
        disabled={!sourceId || !name.trim()}
        busy={busy}
        onClick={submit}
      >
        {busy ? "参照音声を合成しています…" : "この声で話者を作る"}
      </Button>
    </div>
  );
}
