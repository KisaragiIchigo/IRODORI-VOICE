/** エンジンへの問い合わせ。
 *
 * この画面はエンジン自身が /admin/ で配信するため、API は同一オリジンの
 * ルート直下にある。開発サーバーから開いた場合は vite の proxy が中継する。
 * どちらの経路でも先頭スラッシュ付きで届くので、パスはここで固定する。
 *
 * 重みを載せる送信だけは進み具合を出したいので upload.ts（XHR）を通す。
 */

import { detailOf, EngineError, parseJson } from "./errors";
import type { UploadOptions } from "./upload";
import { uploadForm, uploadFormForBlob } from "./upload";
import type {
  InstalledModel,
  BackendStatus,
  CheckpointList,
  CloneRequest,
  ModelBuildResult,
  SeedPreview,
  SeedVoiceRequest,
  Voice,
} from "./types";

const API = "/api";

export { EngineError };

async function unwrap<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
  throw new EngineError(detailOf(parseJson(await response.text()), response.status), response.status);
}

async function getJson<T>(path: string): Promise<T> {
  return unwrap<T>(await fetch(`${API}${path}`, { headers: { Accept: "application/json" } }));
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return unwrap<T>(
    await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  return unwrap<T>(await fetch(`${API}${path}`, { method: "POST", body: form }));
}

export const api = {
  listVoices: () => getJson<Voice[]>("/voices"),

  deleteVoice: async (voiceId: string) =>
    unwrap<void>(await fetch(`${API}/voices/${voiceId}`, { method: "DELETE" })),

  /** 話者のアイコン。付けていない話者も識別色の図形が返るので、常に絵が出る。
   *
   * 差し替えても URL は変わらない。version を進めて取り直させる。
   */
  voiceIconUrl: (voiceId: string, version: number) =>
    `${API}/voices/${voiceId}/icon?v=${version}`,

  setVoiceIcon: (voiceId: string, file: File) => {
    const form = new FormData();
    form.append("icon", file);
    return postForm<Voice>(`/voices/${voiceId}/icon`, form);
  },

  clearVoiceIcon: async (voiceId: string) =>
    unwrap<Voice>(await fetch(`${API}/voices/${voiceId}/icon`, { method: "DELETE" })),

  cloneFromModel: (payload: CloneRequest) => postJson<Voice>("/voices/clone-from-aivm", payload),

  /** 話者を作らずに、シード値の声を試す。本文は wav、測定結果はヘッダから受け取る。 */
  previewSeed: async (
    seed: number,
    text: string,
    caption: string | null,
  ): Promise<{ meta: SeedPreview; blob: Blob }> => {
    const response = await fetch(`${API}/voices/preview-seed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed, text, caption }),
    });
    if (!response.ok) {
      throw new EngineError(
        detailOf(parseJson(await response.text()), response.status),
        response.status,
      );
    }
    const encoded = response.headers.get("X-Irodori-Preview") ?? "";
    const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
    const meta = JSON.parse(new TextDecoder().decode(bytes)) as SeedPreview;
    return { meta, blob: await response.blob() };
  },

  /** シード値だけで話者を作る。音声モデルが 1 つも無くても使える。 */
  createVoiceFromSeed: (payload: SeedVoiceRequest) =>
    postJson<Voice>("/voices/from-seed", payload),

  listModels: () => getJson<InstalledModel[]>("/aivm"),

  /** 対応形式のモデルを 1 ファイル取り込む。 */
  installModel: (file: File, options?: UploadOptions) => {
    const form = new FormData();
    form.append("model", file);
    return uploadForm<InstalledModel>(`${API}/aivm/install`, form, options);
  },

  /** Style-Bert-VITS2 の 3 点セットを取り込む。 */
  installSbv2: (
    name: string,
    model: File,
    config: File,
    styleVectors: File,
    options?: UploadOptions,
  ) => {
    const form = new FormData();
    form.append("name", name);
    form.append("model", model);
    form.append("config", config);
    form.append("style_vectors", styleVectors);
    return uploadForm<InstalledModel>(`${API}/aivm/install-sbv2`, form, options);
  },

  deleteModel: async (uuid: string) =>
    unwrap<void>(await fetch(`${API}/aivm/${uuid}`, { method: "DELETE" })),

  /** 4 点セットから .irvm を組み立てる。本体は Blob、要約はヘッダから受け取る。 */
  buildModel: async (
    form: FormData,
    options?: UploadOptions,
  ): Promise<{ summary: ModelBuildResult; blob: Blob }> => {
    const { blob, header } = await uploadFormForBlob(`${API}/models/build`, form, options);
    const encoded = header("X-Irodori-Model") ?? "";
    // ヘッダは latin-1 しか通らないため base64。日本語を戻すには UTF-8 で復号する。
    const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
    const summary = JSON.parse(new TextDecoder().decode(bytes)) as ModelBuildResult;
    return { summary, blob };
  },

  /** フォルダを指して取り込む。送信が要らないので大きな重みでも待たされない。 */
  buildFromFolder: (directory: string, name?: string) => {
    const params = new URLSearchParams({ directory });
    if (name) {
      params.set("name", name);
    }
    return postForm<ModelBuildResult>(`/models/build-from-folder?${params}`, new FormData());
  },

  listBackends: () => getJson<BackendStatus[]>("/backends"),

  listCheckpoints: () => getJson<CheckpointList>("/models"),

  selectCheckpoint: (checkpoint: string, steps?: number) => {
    const params = new URLSearchParams({ checkpoint });
    if (steps !== undefined) {
      params.set("steps", String(steps));
    }
    return postJson<{ restart_required: boolean; detail: string }>(
      `/models/select?${params}`,
      null,
    );
  },
};
