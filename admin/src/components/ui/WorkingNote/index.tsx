import type { ReactNode } from "react";
import { useEffect, useState } from "react";

type Props = {
  children: ReactNode;
};

/** エンジン側の処理を待っている間の一行。
 *
 * 送信の進み具合は、同じパソコンの中だとすぐ 100% に届いてしまう。実際に待たされるのは
 * その後の読み込みと展開なので、止まって見えないよう経過を数えて出す。
 */
export function WorkingNote({ children }: Props) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((current) => current + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-label text-paper-300" role="status">
      <span className="animate-breathe">{children}</span>
      <span className="font-mono text-paper-400">{seconds} 秒</span>
    </p>
  );
}
