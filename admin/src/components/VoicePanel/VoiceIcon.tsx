import { ImagePlus } from "lucide-react";
import { useRef, useState } from "react";

import { api } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { Voice } from "../../lib/types";
import { VOICE_COLOR_HEX } from "../../lib/types";

/** 受け付ける画像。エンジン側の ALLOWED_ICON_SUFFIXES と対を成す。 */
const ACCEPTED = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];

type Props = {
  voice: Voice;
  /** 差し替えのたびに進む値。同じ URL を取り直させるために使う。 */
  version: number;
  busy: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
};

/** 話者のアイコン。クリックでもドロップでも差し替えられる。
 *
 * 付けていない話者にはエンジンが識別色の図形を返すため、枠が空になることはない。
 * ここに出る絵が、そのままエディタの話者一覧に並ぶ。
 */
export function VoiceIcon({ voice, version, busy, onPick, onClear }: Props) {
  const [hovering, setHovering] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hex = VOICE_COLOR_HEX[voice.color_key] ?? VOICE_COLOR_HEX.shu;

  const accept = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      onPick(file);
    }
  };

  return (
    <div className="flex shrink-0 flex-col items-center gap-1.5">
      <button
        type="button"
        aria-label={`${voice.name} のアイコンを選ぶ`}
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setHovering(true);
        }}
        onDragLeave={() => setHovering(false)}
        onDrop={(event) => {
          event.preventDefault();
          setHovering(false);
          accept(event.dataTransfer.files);
        }}
        className={cn(
          "group relative h-16 w-16 overflow-hidden rounded-lg border shadow-inset transition-colors",
          hovering
            ? "border-beni/50 bg-beni/[0.08] shadow-glow"
            : "border-white/[0.08] bg-black/40 hover:border-white/20",
          busy && "pointer-events-none opacity-40",
        )}
        style={{ boxShadow: hovering ? undefined : `0 0 14px ${hex}22` }}
      >
        <img
          src={api.voiceIconUrl(voice.voice_id, version)}
          alt=""
          className="h-full w-full object-contain"
          draggable={false}
        />
        {/* 触れている間だけ、差し替えられることを知らせる。 */}
        <span
          className={cn(
            "absolute inset-0 flex flex-col items-center justify-center gap-0.5",
            "bg-ground-deep/80 text-paper-200 opacity-0 transition-opacity",
            "group-hover:opacity-100 group-focus-visible:opacity-100",
            hovering && "opacity-100",
          )}
        >
          <ImagePlus className="h-4 w-4 text-paper-300" />
          <span className="text-label leading-none">変更</span>
        </span>
      </button>

      {voice.icon_source === "custom" ? (
        <button
          type="button"
          disabled={busy}
          onClick={onClear}
          className="text-label text-paper-400 underline-offset-2 transition-colors hover:text-beni-pale hover:underline"
        >
          外す
        </button>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        className="hidden"
        onChange={(event) => {
          accept(event.target.files);
          // 同じファイルを選び直したときにも change が起きるようにする。
          event.target.value = "";
        }}
      />
    </div>
  );
}
