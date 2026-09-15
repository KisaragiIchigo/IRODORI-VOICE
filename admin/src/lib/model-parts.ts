/** モデルの材料そろえ。
 *
 * 配布されるファイル名は配布元によって揺れるため、名前ではなく拡張子で見る。
 * 取り込み（3 点）と作成（4 点）で必要な組み合わせが違うので、判定はここへ集約する。
 */

export type ModelParts = {
  /** ハイパーパラメータ。話者とスタイルの定義が入っている。 */
  config?: File;
  /** スタイルベクトル。 */
  styleVectors?: File;
  /** 学習済みの重み。合成に使えるのはこちら。 */
  model?: File;
  /** ONNX 形式の重み。同梱はできるが、現在の合成には使われない。 */
  onnx?: File;
};

export type PartKey = keyof ModelParts;

export function pickParts(files: File[]): ModelParts {
  return {
    config: files.find((file) => file.name.toLowerCase() === "config.json"),
    styleVectors:
      files.find((file) => file.name.toLowerCase() === "style_vectors.npy") ??
      files.find((file) => /\.npy$/i.test(file.name)),
    model: files.find((file) => /\.(safetensors|pth)$/i.test(file.name)),
    onnx: files.find((file) => /\.onnx$/i.test(file.name)),
  };
}

/** 選んだフォルダの名前。話者の呼び名の初期値に使う。 */
export function folderNameOf(files: File[]): string {
  for (const file of files) {
    const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
    const head = path?.split("/")[0];
    if (head) {
      return head;
    }
  }
  return "";
}

/** 合計の大きさ。送る前に、どれくらい待つことになるかを見せるために使う。 */
export function totalSizeOf(parts: ModelParts): number {
  return Object.values(parts).reduce((sum, file) => sum + (file?.size ?? 0), 0);
}
