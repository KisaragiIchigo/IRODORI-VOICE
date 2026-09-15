import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";

type Tone = "accent" | "neutral" | "warning" | "danger" | "success";

const TONES: Record<Tone, string> = {
  accent: "bg-beni/10 text-beni-pale border-beni/20",
  neutral: "bg-white/[0.04] text-paper-300 border-white/[0.06]",
  warning: "bg-shiracha/[0.10] text-shiracha border-shiracha/35",
  danger: "bg-beni/[0.14] text-beni-pale border-beni/35",
  success: "bg-tokiwa-light/[0.18] text-tokiwa-pale border-tokiwa-light/40",
};

type Props = {
  children: ReactNode;
  tone?: Tone;
  className?: string;
};

export function Badge({ children, tone = "neutral", className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5",
        "text-label font-medium tracking-wide whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** 話者の識別色を示す小さな丸。 */
export function ColorDot({ hex, className }: { hex: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-2.5 w-2.5 shrink-0 rounded-full", className)}
      style={{ backgroundColor: hex, boxShadow: `0 0 8px ${hex}55` }}
    />
  );
}
