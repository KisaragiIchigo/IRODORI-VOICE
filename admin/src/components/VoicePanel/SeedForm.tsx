import { Dices, Play } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { messageOf } from "../../lib/errors";
import type { SeedPreview, SeedVoiceRequest } from "../../lib/types";
import { Button } from "../ui/Button";
import { TextField } from "../ui/Field";
import { CaptionField } from "./CaptionField";
import { ColorPicker } from "./ColorPicker";
import { SeedPreviewPanel } from "./SeedPreviewPanel";

/** エンジンが受け付ける上限。schemas.py の VoiceFromSeedRequest と対を成す。 */
const MAX_SEED = 2 ** 31 - 1;
/** 試聴と焼き付けの既定文。voices/reference.py の SEED_REFERENCE_TEXT と同じものを置く。 */
const DEFAULT_TEST_TEXT =
  "こんにちは。今日はいい天気ですね。設定の画面から、音量や話す速さをゆっくり変えられます。";

function randomSeed(): number {
  return Math.floor(Math.random() * (MAX_SEED + 1));
}

type Preview = { url: string; meta: SeedPreview };

type Props = {
  busy: boolean;
  onSubmit: (payload: SeedVoiceRequest) => void;
  onNotify: (kind: "success" | "error" | "info", message: string) => void;
};

/** 音声モデルを持たなくても話者を作れる経路。シードで決めた声を参照音声として焼き付ける。 */
export function SeedForm({ busy, onSubmit, onNotify }: Props) {
  const [name, setName] = useState("");
  const [seed, setSeed] = useState<number>(() => randomSeed());
  const [colorKey, setColorKey] = useState<string>("asagi");
  const [caption, setCaption] = useState("");
  const [testText, setTestText] = useState(DEFAULT_TEST_TEXT);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [testing, setTesting] = useState(false);

  // 差し替えたときと画面を離れるときに、前の音を解放する。
  useEffect(() => {
    if (!preview) return;
    return () => URL.revokeObjectURL(preview.url);
  }, [preview]);

  const seedValid = Number.isInteger(seed) && seed >= 0 && seed <= MAX_SEED;
  const ready = Boolean(name.trim()) && seedValid;

  /** シードや口調を変えたら、前に聴いた音は別物になる。 */
  const invalidate = () => setPreview(null);

  const tryVoice = async () => {
    if (!seedValid) return;
    setTesting(true);
    try {
      const { meta, blob } = await api.previewSeed(
        seed,
        testText.trim() || DEFAULT_TEST_TEXT,
        caption.trim() || null,
      );
      setPreview({ url: URL.createObjectURL(blob), meta });
    } catch (cause) {
      onNotify("error", messageOf(cause, "試聴に失敗しました。"));
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-label leading-relaxed text-paper-400">
        シード値で声を決めて、その声を参照音声として焼き付けます。音声モデルが 1 つも無くても作れます。
        下の「この声を試す」で聴いた音がそのまま話者の声になるため、気に入った音が出たら、
        試す文を変えずに保存してください。作成には十数秒かかります。
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        <TextField
          label="話者の名前"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="例: 〇〇（シード）"
          hint="エディタの話者一覧にこの名前で並びます。"
        />

        <div className="flex flex-col gap-1.5">
          <span className="label-caps">シード値</span>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              max={MAX_SEED}
              value={Number.isFinite(seed) ? seed : ""}
              onChange={(event) => {
                setSeed(event.target.valueAsNumber);
                invalidate();
              }}
              className="min-w-0 flex-1 rounded-md border border-white/[0.06] bg-black/40 px-3 py-2 font-mono text-body text-paper-200 shadow-inset transition-colors focus:border-beni/50 focus:outline-none"
            />
            <Button
              className="shrink-0"
              icon={<Dices className="h-3.5 w-3.5" />}
              onClick={() => {
                setSeed(randomSeed());
                invalidate();
              }}
              disabled={busy || testing}
              aria-label="別の値を引く"
            >
              引き直す
            </Button>
          </div>
          <p className="text-label text-paper-400">
            0 〜 <span className="font-mono">{MAX_SEED.toLocaleString()}</span> の整数です。
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2.5 rounded-md border border-white/[0.04] bg-black/20 p-3">
        <span className="label-caps">声を試す</span>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[18rem] flex-1">
            <TextField
              label="試す文"
              value={testText}
              onChange={(event) => setTestText(event.target.value)}
              placeholder={DEFAULT_TEST_TEXT}
            />
          </div>
          <Button
            variant="primary"
            className="shrink-0 px-4 py-2"
            icon={<Play className="h-3.5 w-3.5" />}
            onClick={() => void tryVoice()}
            disabled={!seedValid || busy}
            busy={testing}
          >
            {testing ? "合成しています…" : "この声を試す"}
          </Button>
        </div>
        <p className="text-label leading-relaxed text-paper-400">
          試しても話者は作られません。ここで読ませた文がそのまま参照音声になるため、
          聴いた音と保存される声が一致します。
        </p>

        {preview ? <SeedPreviewPanel url={preview.url} meta={preview.meta} /> : null}
      </div>

      <ColorPicker value={colorKey} onChange={setColorKey} />

      <CaptionField
        value={caption}
        onChange={(next) => {
          setCaption(next);
          invalidate();
        }}
        includeVoiceTemplates
        hint="読み上げ全体にかかる指定です。焼き付ける声にも反映されるため、変えると声そのものが変わります。試聴にも同じ指定が入ります。"
      />

      <Button
        variant="primary"
        className="self-start px-4 py-2"
        disabled={!ready}
        busy={busy}
        onClick={() =>
          onSubmit({
            name: name.trim(),
            seed,
            color_key: colorKey,
            description: `シード ${seed} から作った話者`,
            caption: caption.trim() || null,
            reference_text: testText.trim() || null,
          })
        }
      >
        {busy ? "声を焼き付けています…" : "このシードで話者を作る"}
      </Button>
    </div>
  );
}
