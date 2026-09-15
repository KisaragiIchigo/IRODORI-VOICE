import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";

type Props = {
  children: ReactNode;
  className?: string;
};

/** アクリル調のパネル。極細の境界線と、わずかな内側の影で奥行きを出す。 */
export function Card({ children, className }: Props) {
  return (
    <div
      className={cn(
        "rounded-lg border border-white/[0.06] bg-white/[0.02] backdrop-blur-md",
        "shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: Props) {
  return (
    <div className={cn("flex items-center justify-between gap-3 border-b border-white/[0.04] px-4 py-3", className)}>
      {children}
    </div>
  );
}

export function CardBody({ children, className }: Props) {
  return <div className={cn("px-4 py-4", className)}>{children}</div>;
}
