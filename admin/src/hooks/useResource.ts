import { useCallback, useEffect, useState } from "react";

import { EngineError } from "../lib/api";

type Resource<T> = {
  data: T;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

/** エンジンから一覧を取ってくるだけの共通処理。
 *
 * 取得に失敗しても画面は保ちたいので、直前のデータは捨てずに error だけ立てる。
 */
export function useResource<T>(fetcher: () => Promise<T>, initial: T): Resource<T> {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetcher());
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof EngineError
          ? cause.message
          : "エンジンに接続できません。起動しているか確認してください。",
      );
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, error, reload };
}
