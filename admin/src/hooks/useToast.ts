import { useCallback, useRef, useState } from "react";

export type ToastKind = "success" | "error" | "info";

export type Toast = {
  id: number;
  kind: ToastKind;
  message: string;
};

/** 画面右下に出す短い通知。失敗は自動で消さない。 */
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current;
      nextId.current += 1;
      setToasts((current) => [...current, { id, kind, message }]);

      // 失敗は読み終える前に消えると原因を追えない。利用者が閉じるまで残す。
      if (kind !== "error") {
        window.setTimeout(() => dismiss(id), 4000);
      }
      return id;
    },
    [dismiss],
  );

  return { toasts, push, dismiss };
}
