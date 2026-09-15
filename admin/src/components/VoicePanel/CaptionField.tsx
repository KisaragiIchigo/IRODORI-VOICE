import type { ReactNode } from "react";

import {
  TONE_TEMPLATES,
  VOICE_TEMPLATES,
  type CaptionTemplate,
} from "../../lib/captionTemplates";
import { SelectField } from "../ui/Field";

type Props = {
  /** モデルへ渡すキャプション。空文字は「指定しない」。 */
  value: string;
  onChange: (caption: string) => void;
  /**
   * 声質のテンプレも並べるか。
   * 参照音声を持つ話者では声の主が参照側で決まるため、声質の指示は競合する。
   */
  includeVoiceTemplates?: boolean;
  hint: ReactNode;
};

/** 表現の指示をテンプレから選ぶ欄。既定は「指定しない」で、従来どおり素の声になる。 */
export function CaptionField({
  value,
  onChange,
  includeVoiceTemplates = false,
  hint,
}: Props) {
  const templates: CaptionTemplate[] = [
    ...(includeVoiceTemplates ? VOICE_TEMPLATES : []),
    ...TONE_TEMPLATES,
  ];
  const selected = templates.find((template) => template.caption === value);

  return (
    <SelectField
      label="表現の指示（任意）"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      hint={selected ? `モデルへは「${selected.caption}」と伝えます。` : hint}
    >
      <option value="">指定しない</option>
      {includeVoiceTemplates ? (
        <optgroup label="声の土台">
          {VOICE_TEMPLATES.map((template) => (
            <option key={template.caption} value={template.caption}>
              {template.label}
            </option>
          ))}
        </optgroup>
      ) : null}
      <optgroup label="話し方">
        {TONE_TEMPLATES.map((template) => (
          <option key={template.caption} value={template.caption}>
            {template.label}
          </option>
        ))}
      </optgroup>
    </SelectField>
  );
}
