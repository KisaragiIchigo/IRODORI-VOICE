/** エンジンからの失敗を、画面へそのまま出せる形にする。
 *
 * fetch 経路（api.ts）と XHR 経路（upload.ts）の両方から使うため、
 * どちらにも依存しないここへ置いている。
 */

/** エンジンが返す失敗。detail に日本語の理由が入る。 */
export class EngineError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "EngineError";
    this.status = status;
  }
}

/** FastAPI は detail に理由を入れる。検証エラーでは配列で返るため両方を扱う。 */
export function detailOf(body: unknown, status: number): string {
  const fallback = `エンジンが ${status} を返しました。`;
  if (typeof body !== "object" || body === null) {
    return fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const joined = detail
      .map((item) => (typeof item === "object" && item !== null ? String((item as { msg?: string }).msg ?? "") : ""))
      .filter(Boolean)
      .join(" / ");
    if (joined) {
      return joined;
    }
  }
  return fallback;
}

/** 本文が JSON でないときは null を返す。 */
export function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** 例外を利用者向けの一文にする。理由が分かっているものはそれを優先する。 */
export function messageOf(cause: unknown, fallback: string): string {
  return cause instanceof EngineError ? cause.message : fallback;
}
