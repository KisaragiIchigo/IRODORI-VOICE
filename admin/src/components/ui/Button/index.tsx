import { m } from "framer-motion";
import type { HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";

type Variant = "primary" | "ghost" | "danger";

// 素の ButtonHTMLAttributes を渡すと、React の onDrag 系と Framer Motion の
// ジェスチャ用ハンドラが同名で衝突する。motion 側の型を土台にして避ける。
type Props = Omit<HTMLMotionProps<"button">, "children"> & {
  variant?: Variant;
  /** 処理中は押せなくし、朱のヘアラインを呼吸させる。 */
  busy?: boolean;
  icon?: ReactNode;
  children?: ReactNode;
};

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-gradient-to-br from-beni via-beni-mid to-beni-deep text-white shadow-glow border-transparent",
  ghost: "bg-white/[0.02] text-paper-300 border-white/[0.06] hover:bg-white/[0.04]",
  danger: "bg-beni/[0.14] text-beni-pale border-beni/35 hover:bg-beni/[0.22]",
};

export function Button({
  variant = "ghost",
  busy = false,
  icon,
  className,
  children,
  disabled,
  ...rest
}: Props) {
  const locked = disabled || busy;

  return (
    <m.button
      type="button"
      whileHover={locked ? undefined : { scale: 1.01 }}
      whileTap={locked ? undefined : { scale: 0.98 }}
      transition={{ type: "spring", stiffness: 420, damping: 30 }}
      disabled={locked}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md border px-3 py-1.5",
        "whitespace-nowrap text-label font-medium tracking-wide transition-colors",
        // 無効時はグレーに潰さず、透明度だけ落とす。何のボタンかは読めたままにする。
        locked && "opacity-40 cursor-not-allowed",
        busy && "animate-breathe",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </m.button>
  );
}
