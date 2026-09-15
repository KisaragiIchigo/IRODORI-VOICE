import { HardDriveUpload } from "lucide-react";
import { useState } from "react";

import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";

type Props = {
  busy: boolean;
  onSubmit: (directory: string, name?: string) => void;
};

/** 場所を渡してエンジンに直接読ませる。数百 MB を送らずに済む。 */
export function FromFolderPath({ busy, onSubmit }: Props) {
  const [directory, setDirectory] = useState("");
  const [name, setName] = useState("");

  return (
    <div className="flex flex-col gap-4">
      <p className="text-label leading-relaxed text-paper-400">
        エンジンが手元のフォルダを直接読みます。ファイルを送らないため、重みが数百 MB ある場合は
        こちらが速く終わります。エンジンと同じパソコンにあるフォルダだけが対象です。
      </p>

      <TextField
        label="フォルダのパス"
        value={directory}
        onChange={(event) => setDirectory(event.target.value)}
        placeholder="C:\Users\you\model_assets\話者名"
        hint="エクスプローラーのアドレス欄をコピーして貼り付けてください。"
      />

      <TextField
        label="話者の呼び名（任意）"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="空のままにするとフォルダ名を使います"
      />

      <Button
        variant="primary"
        className="self-start px-4 py-2"
        icon={<HardDriveUpload className="h-3.5 w-3.5" />}
        onClick={() => onSubmit(directory.trim(), name.trim() || undefined)}
        disabled={!directory.trim()}
        busy={busy}
      >
        取り込む
      </Button>
    </div>
  );
}
