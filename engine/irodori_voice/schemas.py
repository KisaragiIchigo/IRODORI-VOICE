"""HTTP の入出力スキーマ。

エディタは別プロセスなので、ここがシステム境界になる。受け取る値はすべて
Pydantic で範囲まで検証し、バックエンドへは検証済みの値だけを渡す。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .vendor.irodori_tts.duration import ALLOWED_ANNOTATION_EMOJIS
from .voices.reference import SEED_REFERENCE_TEXT

MAX_TEXT_LENGTH = 2000
MAX_CAPTION_LENGTH = 400
MAX_REFERENCE_LINE_LENGTH = 200
# 試聴と焼き付けで読ませる文の上限。長くするほど待ち時間がそのまま伸びる。
MAX_SEED_PREVIEW_LENGTH = 120


class VoiceStyleOut(BaseModel):
    style_id: str
    name: str
    emoji: str | None = None


class VoiceCapabilitiesOut(BaseModel):
    speed: bool
    volume: bool
    pitch: bool
    intonation: bool
    caption: bool
    emoji_style: bool
    reference_audio: bool
    style_strength: bool
    seed: bool
    steps: bool


class VoiceOut(BaseModel):
    voice_id: str
    backend_id: str
    name: str
    description: str
    color_key: str
    styles: list[VoiceStyleOut]
    capabilities: VoiceCapabilitiesOut
    sample_rate: int
    # 一覧に出るアイコンの出どころ。custom は利用者が付けたもの、model は話者が
    # 元から持っていたもの、generated は識別色から描いたもの。
    icon_source: Literal["custom", "model", "generated"]
    is_builtin: bool
    voice_seed: int | None = None
    has_reference: bool = False


class BackendStatusOut(BaseModel):
    backend_id: str
    display_name: str
    available: bool
    detail: str
    install_hint: str | None = None


class HealthOut(BaseModel):
    status: Literal["starting", "ready", "error"]
    model_loaded: bool
    warmed_up: bool
    detail: str
    version: str


class DeviceOut(BaseModel):
    model_device: str
    model_precision: str
    codec_device: str
    codec_precision: str
    available_devices: list[str]
    reason: str


class SynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_id: str = Field(..., min_length=1, max_length=200)
    style_id: str | None = Field(None, max_length=100)

    speed: float = Field(1.0, ge=0.5, le=2.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    pitch: float = Field(0.0, ge=-0.15, le=0.15)
    intonation: float = Field(1.0, ge=0.0, le=2.0)

    pre_silence: float = Field(0.0, ge=0.0, le=10.0)
    post_silence: float = Field(0.1, ge=0.0, le=10.0)

    caption: str | None = Field(None, max_length=MAX_CAPTION_LENGTH)
    style_strength: float = Field(1.0, ge=0.0, le=2.0)
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    steps: int | None = Field(None, ge=1, le=128)


class SynthesisBatchRequest(BaseModel):
    lines: list[SynthesisRequest] = Field(..., min_length=1, max_length=500)
    join_silence: float = Field(0.25, ge=0.0, le=10.0)


class PrefetchRequest(BaseModel):
    line: SynthesisRequest


class PrefetchOut(BaseModel):
    queued: bool
    already_cached: bool


class VoiceStyleIn(BaseModel):
    style_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=80)
    caption: str | None = Field(None, max_length=MAX_CAPTION_LENGTH)
    # 読み上げ文の先頭へ付ける注釈絵文字。Irodori-TTS が解釈できる記号のみ通す。
    emoji: str | None = Field(None, max_length=8)
    duration_scale: float = Field(1.0, ge=0.25, le=4.0)
    cfg_scale_text: float = Field(3.0, ge=0.0, le=15.0)
    cfg_scale_caption: float = Field(3.0, ge=0.0, le=15.0)
    cfg_scale_speaker: float = Field(5.0, ge=0.0, le=15.0)
    num_steps: int | None = Field(None, ge=1, le=128)

    @field_validator("emoji")
    @classmethod
    def _check_emoji(cls, value: str | None) -> str | None:
        """モデルが解釈できる記号だけを通す。

        知らない絵文字は注釈として扱われず、読み上げ対象の文字として
        音に混ざる。ここで弾かないと「付けたのに効かない」ではなく
        「変な音が入る」形で表に出る。
        """

        if value is None or value == "":
            return None
        if value not in ALLOWED_ANNOTATION_EMOJIS:
            raise ValueError(
                f"Irodori-TTS が注釈として扱えない絵文字です: {value}"
            )
        return value


class VoiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=300)
    color_key: str = Field("shu", min_length=1, max_length=40)
    mode: Literal["reference", "caption", "embed"] = "caption"
    styles: list[VoiceStyleIn] = Field(..., min_length=1, max_length=32)


class VoiceFromSeedRequest(BaseModel):
    """シード値を指定して話者を作る。

    シードの声を 1 本合成し、それを参照音声として焼き付けた話者になる。
    ``reference_text`` はそのとき読ませる文で、試聴に使った文をそのまま渡せば、
    聴いたとおりの声が保存される。
    """

    name: str = Field(..., min_length=1, max_length=80)
    seed: int = Field(..., ge=0, le=2**31 - 1)
    description: str = Field("", max_length=300)
    color_key: str = Field("shu", min_length=1, max_length=40)
    caption: str | None = Field(None, max_length=MAX_CAPTION_LENGTH)
    reference_text: str | None = Field(None, min_length=1, max_length=MAX_SEED_PREVIEW_LENGTH)


class VoiceBakeReferenceRequest(BaseModel):
    """参照音声を持たない話者へ、あとから声を焼き付ける。"""

    reference_text: str | None = Field(None, min_length=1, max_length=MAX_SEED_PREVIEW_LENGTH)


class SeedPreviewRequest(BaseModel):
    """話者を作らずに、シード値の声を試す。

    保存の前に声を確かめるための入口。合成そのものは通常の経路を通る。
    既定文は焼き付けに使う文と同じで、試聴した直後に作れば同じ音がそのまま参照になる。
    """

    seed: int = Field(..., ge=0, le=2**31 - 1)
    text: str = Field(SEED_REFERENCE_TEXT, min_length=1, max_length=MAX_SEED_PREVIEW_LENGTH)
    caption: str | None = Field(None, max_length=MAX_CAPTION_LENGTH)


class VoiceCloneFromModelRequest(BaseModel):
    """取り込んだ話者の声を写した Irodori-TTS 話者を作る。

    参照文はエンジン側の既定を使うのが基本で、指定できるのは声の癖が
    出にくい文に差し替えたい場合のため。合計 30 秒を超えた分は捨てられる。
    """

    source_voice_id: str = Field(..., min_length=1, max_length=200)
    source_style_id: str | None = Field(None, max_length=100)
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=300)
    color_key: str = Field("shu", min_length=1, max_length=40)
    reference_lines: list[str] | None = Field(None, min_length=1, max_length=12)
    with_emotion_styles: bool = True
    # ノーマルのスタイルへ入れる口調の指示。喜怒哀楽のスタイルは固有の指示を持つため触らない。
    caption: str | None = Field(None, max_length=MAX_CAPTION_LENGTH)

    @field_validator("reference_lines")
    @classmethod
    def _check_lines(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [line.strip() for line in value if line.strip()]
        if not cleaned:
            raise ValueError("参照文がすべて空です。")
        for line in cleaned:
            if len(line) > MAX_REFERENCE_LINE_LENGTH:
                raise ValueError(
                    f"参照文は 1 行 {MAX_REFERENCE_LINE_LENGTH} 文字までです。"
                )
        return cleaned


class VoiceUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    color_key: str | None = Field(None, min_length=1, max_length=40)
    styles: list[VoiceStyleIn] | None = Field(None, min_length=1, max_length=32)
    voice_seed: int | None = Field(None, ge=0, le=2**31 - 1)


class ModelSpeakerOut(BaseModel):
    uuid: str
    name: str
    local_id: int
    styles: list[VoiceStyleOut]


class ModelOut(BaseModel):
    uuid: str
    name: str
    description: str
    creators: list[str]
    license: str | None
    model_architecture: str
    model_format: str
    version: str
    speakers: list[ModelSpeakerOut]
    # 合成に使えるか。ONNX 形式は取り込めても合成できない。
    usable: bool = True
    note: str | None = None


class TextSplitRequest(BaseModel):
    """長文を行へ割る要求。既定値はエンジンが合成時に使う設定と同じ。"""

    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH * 10)
    target_chars: int = Field(38, ge=10, le=200)
    max_chars: int = Field(60, ge=20, le=300)


class TextSplitSegmentOut(BaseModel):
    index: int
    text: str
    chars: int
    # 短い行は音が崩れやすい。貼り付ける前に気付けるよう印を付ける。
    is_short: bool


class TextSplitOut(BaseModel):
    segments: list[TextSplitSegmentOut]
    # そのまま貼り付けられるよう、改行で繋いだものも返す。
    joined: str
    total_chars: int
    short_line_count: int
    short_line_threshold: int


class ModelBuildOut(BaseModel):
    """組み立てた音声モデルの要約。"""

    uuid: str
    name: str
    model_architecture: str
    # 同梱した重み。合成に使えるのは Safetensors 側だけ。
    has_safetensors: bool
    has_onnx: bool
    speaker_count: int
    style_count: int
    size_bytes: int
    # ライブラリへ取り込んだか。false なら手元のファイルとして受け取っただけ。
    installed: bool
    file_name: str


class SettingsOut(BaseModel):
    checkpoint: str
    model_device: str
    model_precision: str
    codec_device: str
    codec_precision: str
    num_steps: int | None
    runtime_pool_size: int
    reference_latent_cache: bool
    warmup_on_start: bool


class SettingsUpdateRequest(BaseModel):
    checkpoint: str | None = Field(None, min_length=1, max_length=300)
    model_device: Literal["auto", "cuda", "cpu", "mps", "xpu"] | None = None
    model_precision: Literal["auto", "fp32", "bf16"] | None = None
    codec_device: Literal["auto", "cuda", "cpu", "mps", "xpu"] | None = None
    codec_precision: Literal["auto", "fp32", "bf16"] | None = None
    num_steps: int | None = Field(None, ge=1, le=128)
    runtime_pool_size: int | None = Field(None, ge=1, le=4)
    reference_latent_cache: bool | None = None
    warmup_on_start: bool | None = None
