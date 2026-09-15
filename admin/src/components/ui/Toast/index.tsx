import { AnimatePresence, m } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { cn } from "../../../lib/cn";
import type { Toast as ToastData, ToastKind } from "../../../hooks/useToast";

const TONES: Record<ToastKind, string> = {
  success: "border-tokiwa-light/40 bg-tokiwa-light/[0.18] text-tokiwa-pale",
  error: "border-beni/35 bg-beni/[0.14] text-beni-pale",
  info: "border-white/[0.06] bg-white/[0.04] text-paper-200",
};

const ICONS: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

type Props = {
  toasts: ToastData[];
  onDismiss: (id: number) => void;
};

export function ToastStack({ toasts, onDismiss }: Props) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-40 flex w-[min(26rem,calc(100vw-2rem))] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind];
          return (
            <m.div
              key={toast.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className={cn(
                "pointer-events-auto flex items-start gap-2.5 rounded-lg border px-3 py-2.5 backdrop-blur-md",
                TONES[toast.kind],
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="flex-1 text-label leading-relaxed">{toast.message}</p>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="shrink-0 rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
                aria-label="閉じる"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </m.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
