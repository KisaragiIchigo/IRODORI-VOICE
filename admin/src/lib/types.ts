/** エンジンの HTTP スキーマに対応する型。engine/irodori_voice/schemas.py と対を成す。 */

export type VoiceStyle = {
  style_id: string;
  name: string;
  /** 読み上げ文へ添える注釈絵文字。Irodori-TTS が表現の指示として解釈する。 */
  emoji?: string | null;
};

export type VoiceCapabilities = {
  speed: boolean;
  volume: boolean;
  pitch: boolean;
  intonation: boolean;
  caption: boolean;
  emoji_style: boolean;
  reference_audio: boolean;
  style_strength: boolean;
  seed: boolean;
  steps: boolean;
};

/** アイコンの出どころ。generated は識別色から描いた図形。 */
export type IconSource = "custom" | "model" | "generated";

export type Voice = {
  voice_id: string;
  backend_id: "irodori" | "aivm";
  name: string;
  description: string;
  color_key: string;
  styles: VoiceStyle[];
  capabilities: VoiceCapabilities;
  sample_rate: number;
  /** 一覧に出るアイコンの出どころ。custom は付けたもの、model は話者が元から持つもの。 */
  icon_source: IconSource;
  is_builtin: boolean;
  voice_seed: number | null;
  /** 実際に参照音声を持っているか。capabilities.reference_audio は対応可否なので別物。 */
  has_reference: boolean;
  /** 利用者が書いた覚え書き。合成には使わず、この画面にだけ出る。 */
  memo: string;
};

/** 話者の書き換え。触る項目だけを送る。 */
export type VoiceUpdate = {
  name?: string;
  description?: string;
  /** 空文字はメモを消す意味になる。未指定（省略）と区別される。 */
  memo?: string;
  color_key?: string;
};

export type ModelSpeaker = {
  uuid: string;
  name: string;
  local_id: number;
  styles: VoiceStyle[];
};

export type InstalledModel = {
  uuid: string;
  name: string;
  description: string;
  creators: string[];
  license: string | null;
  model_architecture: string;
  model_format: string;
  version: string;
  speakers: ModelSpeaker[];
  /** ONNX 形式は取り込めても合成に使えない。false のときは note に理由が入る。 */
  usable: boolean;
  note: string | null;
};

export type BackendStatus = {
  backend_id: string;
  display_name: string;
  available: boolean;
  detail: string;
  install_hint: string | null;
};

export type Checkpoint = {
  checkpoint: string;
  label: string;
  detail: string;
  recommended_steps: number | null;
  downloaded: boolean;
  selected: boolean;
};

export type CheckpointList = {
  current: string;
  current_steps: number | null;
  checkpoints: Checkpoint[];
};

/** 漢字語を読みへ置き換えてからモデルへ渡すか。 */
export type PronunciationMode = "off" | "kanji";

export type EngineSettings = {
  checkpoint: string;
  model_device: string;
  model_precision: string;
  codec_device: string;
  codec_precision: string;
  num_steps: number | null;
  pronunciation_mode: PronunciationMode;
  runtime_pool_size: number;
  reference_latent_cache: boolean;
  warmup_on_start: boolean;
};

export type ModelBuildResult = {
  uuid: string;
  name: string;
  model_architecture: string;
  /** 同梱した重み。合成に使えるのは Safetensors 側だけ。 */
  has_safetensors: boolean;
  has_onnx: boolean;
  speaker_count: number;
  style_count: number;
  size_bytes: number;
  installed: boolean;
  file_name: string;
};

export type SeedPitch = {
  /** 有声フレームの中央値。 */
  median_hz: number;
  low_hz: number;
  high_hz: number;
  /** 有声と判定した割合。低いほど測定が頼りない。 */
  voiced_ratio: number;
  label: string;
  note: string;
};

export type SeedPreview = {
  seed: number;
  used_seed: number;
  sample_rate: number;
  duration_seconds: number;
  /** 声が短すぎるなどで測れなかったときは null。 */
  pitch: SeedPitch | null;
};

export type SeedVoiceRequest = {
  source_voice_id?: string | null;
  name: string;
  /** 0 〜 2147483647。この値から声が決まる。 */
  seed: number;
  description?: string;
  color_key?: string;
  /** 表現の指示。空にすると素の声になる。 */
  caption?: string | null;
  /** 焼き付けるときに読ませる文。試聴に使った文を渡すと、聴いた声がそのまま残る。 */
  reference_text?: string | null;
  /** 喜怒哀楽のスタイルも作るか。声を借りるときと同じ顔ぶれが付く。 */
  with_emotion_styles?: boolean;
};

export type CloneRequest = {
  source_voice_id: string;
  source_style_id?: string | null;
  name: string;
  description?: string;
  color_key?: string;
  reference_lines?: string[] | null;
  with_emotion_styles?: boolean;
  /** ノーマルのスタイルにだけ入る口調の指示。 */
  caption?: string | null;
};

/** 話者の識別色。エンジンの color_key と対応する。 */
export const VOICE_COLORS = [
  "shu",
  "yamabuki",
  "wakatake",
  "asagi",
  "rurikon",
  "fuji",
  "kobai",
  "sumire",
] as const;

export type VoiceColor = (typeof VOICE_COLORS)[number];

export const VOICE_COLOR_HEX: Record<string, string> = {
  shu: "#b94047",
  yamabuki: "#e0a13a",
  wakatake: "#66b070",
  asagi: "#3fa4b8",
  rurikon: "#5a72c9",
  fuji: "#9a76d0",
  kobai: "#dd6f95",
  sumire: "#7c86a8",
};
