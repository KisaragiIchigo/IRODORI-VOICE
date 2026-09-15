"""VOICEVOX ENGINE 互換 API のスキーマ。

フィールド名は VOICEVOX ENGINE の公開仕様に合わせて camelCase のまま定義する。
外部ツール（ゆっくりMovieMaker、AviUtl プラグインなど）は生成された JSON を
そのまま往復させるため、名前が 1 文字でも違うと繋がらない。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# VOICEVOX の既定出力。外部ツールはこの値を前提に持っていることがある。
DEFAULT_OUTPUT_SAMPLING_RATE = 24000


class Mora(BaseModel):
    """モーラ（子音 + 母音）1 つ分。"""

    text: str
    consonant: str | None = None
    consonant_length: float | None = None
    vowel: str
    vowel_length: float
    pitch: float


class AccentPhrase(BaseModel):
    """アクセント句。``accent`` はアクセント核の位置（1 始まり、0 は平板）。"""

    moras: list[Mora]
    accent: int
    pause_mora: Mora | None = None
    is_interrogative: bool = False


class AudioQuery(BaseModel):
    accent_phrases: list[AccentPhrase]
    speedScale: float = 1.0
    pitchScale: float = 0.0
    intonationScale: float = 1.0
    volumeScale: float = 1.0
    prePhonemeLength: float = 0.1
    postPhonemeLength: float = 0.1
    pauseLength: float | None = None
    pauseLengthScale: float = 1.0
    outputSamplingRate: int = DEFAULT_OUTPUT_SAMPLING_RATE
    outputStereo: bool = False
    kana: str | None = None


class SpeakerStyle(BaseModel):
    name: str
    id: int
    type: str = "talk"


class SpeakerSupportedFeatures(BaseModel):
    permitted_synthesis_morphing: str = "NOTHING"


class Speaker(BaseModel):
    name: str
    speaker_uuid: str
    styles: list[SpeakerStyle]
    version: str
    supported_features: SpeakerSupportedFeatures = Field(
        default_factory=SpeakerSupportedFeatures
    )


class StyleInfo(BaseModel):
    id: int
    icon: str
    voice_samples: list[str] = Field(default_factory=list)


class SpeakerInfo(BaseModel):
    policy: str
    portrait: str
    style_infos: list[StyleInfo]


class SupportedDevices(BaseModel):
    cpu: bool = True
    cuda: bool = False
    dml: bool = False
