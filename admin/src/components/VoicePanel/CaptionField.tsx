import type { ReactNode } from "react";
import type { Voice } from "../../lib/types";

import { TONE_TEMPLATES } from "../../lib/captionTemplates";
import { SelectField } from "../ui/Field";

type Props = {
  /** モデルへ渡すキャプション。空文字は「指定しない」。 */
  value: string;
  onChange: (caption: string) => void;
  sourceSelection?: {
    voices: Voice[];
    value: string;
    onChange: (voiceId: string) => void;
  };
  hint: ReactNode;
};

/** 表現の指示をテンプレから選ぶ欄。既定は「指定しない」で、従来どおり素の声になる。 */
export function CaptionField({
  value,
  onChange,
  sourceSelection,
  hint,
}: Props) {
  const templates = sourceSelection ? [] : TONE_TEMPLATES;
  const selected = templates.find((template) => template.caption === value);
  const sourceId = sourceSelection?.value ?? "";
  const source = sourceSelection?.voices.find((voice) => voice.voice_id === sourceId);

  return (
    <SelectField
      label="表現の指示（任意）"
      value={sourceId ? `model:${sourceId}` : value ? `caption:${value}` : ""}
      onChange={(event) => {
        const next = event.target.value;
        if (next.startsWith("model:")) {
          onChange("");
          sourceSelection?.onChange(next.slice(6));
        } else {
          sourceSelection?.onChange("");
          onChange(next ? next.slice(8) : "");
        }
      }}
      hint={sourceId
        ? source
          ? `${source.name} の基本スタイルを使います。声質はシードから生成します。元の参照音声は使いません。`
          : "選択したモデルが見つかりません。選び直してください。"
        : selected ? `モデルへは「${selected.caption}」と伝えます。` : hint}
    >
      <option value="">指定しない</option>
      {!sourceSelection ? (
        <optgroup label="話し方">
          {templates.map((template) => (
            <option key={template.caption} value={`caption:${template.caption}`}>
              {template.label}
            </option>
          ))}
        </optgroup>
      ) : null}
      {sourceId && !source ? (
        <option value={`model:${sourceId}`} disabled>削除されたモデル（選び直してください）</option>
      ) : null}
      {sourceSelection && sourceSelection.voices.length > 0 ? (
        <optgroup label="登録済みIRODORIモデル">
          {sourceSelection.voices.map((voice) => (
            <option key={voice.voice_id} value={`model:${voice.voice_id}`}>
              {voice.name}
            </option>
          ))}
        </optgroup>
      ) : null}
    </SelectField>
  );
}
