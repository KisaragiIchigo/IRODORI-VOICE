"""出力形式を整える。

サンプリングレートの変換とステレオ化は、連結が終わった最後に 1 度だけ行う。
区間ごとに変換すると、境目で位相が揃わず継ぎ目が目立つ。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ... import audio as audio_utils


@dataclass(frozen=True)
class OutputFormat:
    sample_rate: int | None = None
    stereo: bool = True


@dataclass
class FormattedAudio:
    wav: bytes
    sample_rate: int
    duration_seconds: float


def apply_output_format(
    samples: np.ndarray,
    *,
    source_rate: int,
    output: OutputFormat,
) -> FormattedAudio:
    target_rate = int(output.sample_rate or source_rate)
    converted = samples
    if target_rate != source_rate:
        converted = audio_utils.resample(
            samples, source_rate=source_rate, target_rate=target_rate
        )

    wav = (
        audio_utils.encode_wav_stereo(converted, sample_rate=target_rate)
        if output.stereo
        else audio_utils.encode_wav(converted, sample_rate=target_rate)
    )
    duration = len(converted) / float(target_rate) if target_rate else 0.0
    return FormattedAudio(wav=wav, sample_rate=target_rate, duration_seconds=duration)
