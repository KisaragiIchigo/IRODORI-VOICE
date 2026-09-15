/** 進み具合の分かる送信。
 *
 * モデルの重みは数百 MB になる。fetch では送信中の量を取れず、押してから
 * 数分間まったく反応が無い画面になってしまうため、この経路だけ XHR を使う。
 */

import { detailOf, EngineError, parseJson } from "./errors";

export type UploadProgress = {
  loaded: number;
  /** 総量。0 のときは求められなかったことを表す。 */
  total: number;
};

export type UploadOptions = {
  onProgress?: (progress: UploadProgress) => void;
};

async function messageOfFailure(request: XMLHttpRequest): Promise<string> {
  const raw: unknown = request.response;
  if (raw instanceof Blob) {
    return detailOf(parseJson(await raw.text()), request.status);
  }
  if (typeof raw === "string") {
    return detailOf(parseJson(raw), request.status);
  }
  return detailOf(raw, request.status);
}

function send(
  url: string,
  form: FormData,
  responseType: "json" | "blob",
  options: UploadOptions,
): Promise<XMLHttpRequest> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.responseType = responseType;

    request.upload.addEventListener("progress", (event) => {
      options.onProgress?.({
        loaded: event.loaded,
        total: event.lengthComputable ? event.total : 0,
      });
    });

    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request);
        return;
      }
      void messageOfFailure(request).then((message) => {
        reject(new EngineError(message, request.status));
      });
    });

    request.addEventListener("error", () => {
      reject(new EngineError("エンジンへ送れませんでした。起動しているか確認してください。", 0));
    });

    request.addEventListener("timeout", () => {
      reject(new EngineError("送信が時間切れになりました。", 0));
    });

    request.send(form);
  });
}

/** JSON を返す送信。 */
export async function uploadForm<T>(
  url: string,
  form: FormData,
  options: UploadOptions = {},
): Promise<T> {
  const request = await send(url, form, "json", options);
  return request.response as T;
}

/** ファイルを返す送信。要約はヘッダから受け取る。 */
export async function uploadFormForBlob(
  url: string,
  form: FormData,
  options: UploadOptions = {},
): Promise<{ blob: Blob; header: (name: string) => string | null }> {
  const request = await send(url, form, "blob", options);
  return {
    blob: request.response as Blob,
    header: (name) => request.getResponseHeader(name),
  };
}
