import { AudioLines } from "lucide-react";

import type { SeedPreview } from "../../lib/types";

type Props = {
  url: string;
  meta: SeedPreview;
};

/** 試した声の再生と、測った高さ。 */
export function SeedPreviewPanel({ url, meta }: Props) {
  const pitch = meta.pitch;

  return (
    <div className="flex flex-col gap-3 rounded-md border border-tokiwa-light/40 bg-tokiwa-light/[0.16] px-3 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="label-caps flex shrink-0 items-center gap-1.5 text-tokiwa-pale">
          <AudioLines className="h-3.5 w-3.5" />
          シード {meta.seed} の声
        </span>
        <span className="font-mono text-label text-paper-400">
          {meta.duration_seconds.toFixed(2)} 秒
        </span>
      </div>

      {/* ブラウザ標準の再生操作をそのまま使う。作る前に何度でも聴き直せる。 */}
      <audio src={url} controls autoPlay className="w-full" />

      {pitch ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="label-caps shrink-0">声の高さ</span>
            <span className="font-mono text-body text-paper-100">
              {pitch.median_hz.toFixed(0)} Hz
            </span>
            <span className="rounded bg-beni/[0.12] px-1.5 py-0.5 text-label text-beni-pale">
              {pitch.label}
            </span>
            <span className="font-mono text-label text-paper-400">
              抑揚 {pitch.low_hz.toFixed(0)}〜{pitch.high_hz.toFixed(0)} Hz
            </span>
          </div>
          <p className="text-label leading-relaxed text-paper-400">
            {pitch.note}
            声の高さは目安です。話者の性別や年齢と必ずしも対応しません。
          </p>
        </div>
      ) : (
        <p className="text-label leading-relaxed text-paper-400">
          声が短く、高さを測れませんでした。試す文を少し長くすると測定できます。
        </p>
      )}
    </div>
  );
}
