import { FolderOpen } from "lucide-react";
import { useRef, useState } from "react";

import { formatSize } from "../../../lib/format";
import { folderNameOf, pickParts, totalSizeOf } from "../../../lib/model-parts";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { PartChecklist } from "./PartChecklist";

type Props = {
  busy: boolean;
  onSubmit: (name: string, model: File, config: File, styleVectors: File) => void;
};

/** 学習フォルダの中身を送って取り込む。フォルダ名から呼び名を先に埋めておく。 */
export function FromFolderUpload({ busy, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<File[] | null>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const parts = picked ? pickParts(picked) : null;
  const ready = Boolean(parts?.model && parts?.config && parts?.styleVectors && name.trim());

  const submit = () => {
    if (parts?.model && parts.config && parts.styleVectors && name.trim()) {
      onSubmit(name.trim(), parts.model, parts.config, parts.styleVectors);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-label leading-relaxed text-paper-400">
        学習時の <code className="font-mono text-paper-300">model_assets/話者名/</code>{" "}
        フォルダをそのまま選んでください。中から必要なファイルを拾います。モデル本体だけでは
        話者名もスタイルも分からないため、フォルダごと指定する必要があります。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          icon={<FolderOpen className="h-3.5 w-3.5" />}
          onClick={() => folderRef.current?.click()}
          disabled={busy}
        >
          フォルダを選ぶ
        </Button>
        {parts ? (
          <span className="text-label text-paper-400">
            合計 <span className="font-mono text-paper-300">{formatSize(totalSizeOf(parts))}</span> を送ります
          </span>
        ) : (
          <span className="text-label text-paper-400">まだ選ばれていません</span>
        )}
      </div>

      {parts ? <PartChecklist parts={parts} /> : null}

      {parts && !parts.model && parts.onnx ? (
        <p className="rounded-md border border-shiracha/35 bg-shiracha/[0.10] px-3 py-2 text-label leading-relaxed text-shiracha">
          ONNX 形式の重みだけが見つかりました。この経路では取り込めません。「モデルを作成」から
          .irvm へまとめてください。
        </p>
      ) : null}

      <TextField
        label="話者の呼び名"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="例: 話者の名前"
        hint="この名前で話者一覧に並びます。"
      />

      <Button variant="primary" className="self-start px-4 py-2" onClick={submit} disabled={!ready} busy={busy}>
        取り込む
      </Button>

      <input
        ref={folderRef}
        type="file"
        multiple
        webkitdirectory=""
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          setPicked(files);
          // フォルダ名がそのまま呼び名になることが多い。書き換えたものは残す。
          setName((current) => current || folderNameOf(files));
          event.target.value = "";
        }}
      />
    </div>
  );
}
