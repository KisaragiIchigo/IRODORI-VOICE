import { cn } from "../../../lib/cn";
import { formatProgress } from "../../../lib/format";

type Props = {
  loaded: number;
  total: number;
  /** 何を送っているか。行の左端に置く。 */
  label: string;
  className?: string;
};

/** 送信の進み具合。極細のトラックに朱が伸び、右端の数値だけが発光する。 */
export function Progress({ loaded, total, label, className }: Props) {
  const ratio = total > 0 ? Math.min(1, loaded / total) : 0;
  const percent = Math.round(ratio * 100);
  // 総量が取れないときは、伸びない棒の代わりに呼吸させる。
  const indeterminate = total <= 0;

  return (
    <div className={cn("flex flex-col gap-1.5", className)} role="status" aria-live="polite">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-label text-paper-300">{label}</span>
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-label text-paper-400">
            {formatProgress(loaded, total)}
          </span>
          {indeterminate ? null : (
            <span className="rounded bg-beni/10 px-1.5 py-0.5 font-mono text-label text-beni-pale">
              {percent}%
            </span>
          )}
        </span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.06] shadow-inset">
        <div
          className={cn(
            "h-full rounded-full bg-gradient-to-r from-beni-deep via-beni-mid to-beni shadow-glow",
            indeterminate ? "w-1/3 animate-breathe" : "transition-[width] duration-200 ease-out",
          )}
          style={indeterminate ? undefined : { width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
