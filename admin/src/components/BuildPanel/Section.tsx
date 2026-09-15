import type { ReactNode } from "react";

type Props = {
  /** 手順の番号。作業の順序をここだけで示す。 */
  step: number;
  title: string;
  /** 見出しの右端へ置く補足。状態の一言に使う。 */
  aside?: ReactNode;
  children: ReactNode;
};

/** 番号つきの区切り。見出しから右へヘアラインを伸ばして、間を空けずに区切る。 */
export function Section({ step, title, aside, children }: Props) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-beni/25 bg-beni/[0.08] font-mono text-label text-beni-pale">
          {step}
        </span>
        <h3 className="label-caps shrink-0 text-paper-300">{title}</h3>
        <span aria-hidden className="h-px min-w-4 flex-1 bg-white/[0.06]" />
        {aside}
      </div>
      {children}
    </section>
  );
}
