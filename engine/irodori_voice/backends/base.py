"""合成バックエンドの共通インターフェース。

Irodori-TTS と Style-Bert-VITS2 はパラメータの語彙がまったく違う。
UI 側に分岐を漏らさないため、ここで「何ができるか」を ``VoiceCapabilities`` として
宣言させ、対応しないパラメータは受け取っても無視する契約にしている。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class VoiceCapabilities:
    """話者が実際に受け付けるパラメータの宣言。

    UI はこのフラグだけを見てコントロールの出し分けを行う。対応しないパラメータを
    それらしく見せて内部で捨てると、利用者が「効かないつまみ」を触り続けることになる。
    """

    speed: bool = True
    volume: bool = True
    pitch: bool = False
    intonation: bool = False
    caption: bool = False
    emoji_style: bool = False
    reference_audio: bool = False
    style_strength: bool = False
    seed: bool = True
    steps: bool = False


@dataclass(frozen=True)
class VoiceStyle:
    style_id: str
    name: str
    # 読み上げ文へ添える注釈絵文字。持たないスタイルもある。
    emoji: str | None = None


@dataclass(frozen=True)
class VoiceInfo:
    voice_id: str
    backend_id: str
    name: str
    description: str
    color_key: str
    styles: list[VoiceStyle]
    capabilities: VoiceCapabilities
    sample_rate: int
    # 話者そのものが持っている画像。取り込んだモデルはマニフェストのアイコン、Irodori-TTS は
    # 取り込み時に添えた画像。利用者が付けたアイコンはこことは別に保管する。
    portrait_path: str | None = None
    is_builtin: bool = False
    # 話者に固定された声のシード。参照音声を持つ話者では意味を持たない。
    voice_seed: int | None = None
    # 実際に参照音声を持っているか。``capabilities.reference_audio`` は
    # 「受け付けられるか」を表すので、持っているかどうかとは別に持つ。
    has_reference: bool = False


@dataclass(frozen=True)
class BackendAvailability:
    """バックエンドが使える状態かどうかと、使えない場合の対処法。"""

    backend_id: str
    available: bool
    display_name: str
    detail: str
    install_hint: str | None = None


@dataclass(frozen=True)
class SynthesisParams:
    """1 行ぶんの合成要求。バックエンド非依存の語彙で表現する。"""

    text: str
    voice_id: str
    style_id: str | None = None

    speed: float = 1.0
    volume: float = 1.0
    pitch: float = 0.0
    intonation: float = 1.0

    pre_silence: float = 0.0
    post_silence: float = 0.1

    caption: str | None = None
    style_strength: float = 1.0
    seed: int | None = None
    steps: int | None = None

    def cache_fingerprint(self) -> tuple:
        """同一出力になる要求を突き合わせるためのキー。

        seed=None は毎回異なる音を意図しているのでキャッシュ対象から外す。
        その判定は呼び出し側が行い、ここでは値をそのまま並べる。
        """

        return (
            self.text,
            self.voice_id,
            self.style_id,
            round(self.speed, 4),
            round(self.volume, 4),
            round(self.pitch, 4),
            round(self.intonation, 4),
            round(self.pre_silence, 4),
            round(self.post_silence, 4),
            self.caption,
            round(self.style_strength, 4),
            self.seed,
            self.steps,
        )


@dataclass
class SynthesisOutput:
    samples: np.ndarray
    sample_rate: int
    used_seed: int
    stage_timings: list[tuple[str, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class BackendError(RuntimeError):
    """バックエンド側の失敗。HTTP 層で 400/503 に変換される。"""

    def __init__(self, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.recoverable = recoverable


@runtime_checkable
class SynthesisBackend(Protocol):
    backend_id: str

    def availability(self) -> BackendAvailability: ...

    def list_voices(self) -> list[VoiceInfo]: ...

    def synthesize(self, params: SynthesisParams) -> SynthesisOutput: ...

    def warmup(self) -> None: ...

    def shutdown(self) -> None: ...
