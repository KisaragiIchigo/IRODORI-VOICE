import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** 見出しの下へ置く一文。何をする画面かをここで言い切る。 */
  description?: string;
  /** 閉じてよいか。送信中は閉じさせない。 */
  dismissible?: boolean;
  className?: string;
  children: ReactNode;
};

/** 墨の地に浮かぶパネル。背後は暗く沈めて、手前の操作だけに視線を残す。 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  dismissible = true,
  className,
  children,
}: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-[2px] animate-veil-in" />
        <Dialog.Content
          onInteractOutside={(event) => {
            if (!dismissible) event.preventDefault();
          }}
          onEscapeKeyDown={(event) => {
            if (!dismissible) event.preventDefault();
          }}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[min(46rem,calc(100vw-2rem))]",
            "-translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl",
            "border border-white/[0.08] bg-ground shadow-[0_24px_64px_rgba(0,0,0,0.6)]",
            "animate-dialog-in focus:outline-none",
            className,
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b border-white/[0.06] px-5 py-3.5">
            <div className="flex flex-col gap-1">
              <Dialog.Title className="text-body font-medium text-paper-100">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="text-label leading-relaxed text-paper-400">
                  {description}
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close
              disabled={!dismissible}
              className={cn(
                "-mr-1 shrink-0 rounded-md p-1.5 text-paper-400 transition-colors",
                "hover:bg-white/[0.06] hover:text-paper-200",
                !dismissible && "opacity-30",
              )}
              aria-label="閉じる"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
