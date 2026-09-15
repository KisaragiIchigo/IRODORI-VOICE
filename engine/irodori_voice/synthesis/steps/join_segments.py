"""区間ごとの波形を 1 本へ繋ぐ。

区間をまたいでサンプリングレートが変わることは通常ないが、バックエンドを
跨いだ場合に備えて最初の区間のレートへ揃える。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ... import audio as audio_utils
from ...backends.base import SynthesisOutput


@dataclass
class JoinedAudio:
    samples: np.ndarray
    sample_rate: int
    used_seed: int
    stage_timings: list[tuple[str, float]]
    notes: list[str]


def join_segments(outputs: list[SynthesisOutput]) -> JoinedAudio:
    """区間の出力を順に連結する。

    無音の挿入は区間ごとのパラメータ（post_silence）で済んでいるため、
    ここでは並べるだけに徹する。
    """

    if not outputs:
        raise ValueError("連結する区間がありません。")

    if len(outputs) == 1:
        single = outputs[0]
        return JoinedAudio(
            samples=single.samples,
            sample_rate=single.sample_rate,
            used_seed=single.used_seed,
            stage_timings=list(single.stage_timings),
            notes=list(single.notes),
        )

    sample_rate = outputs[0].sample_rate
    pieces: list[np.ndarray] = []
    timings: dict[str, float] = {}
    notes: list[str] = []

    for output in outputs:
        samples = output.samples
        if output.sample_rate != sample_rate:
            samples = audio_utils.resample(
                samples, source_rate=output.sample_rate, target_rate=sample_rate
            )
        pieces.append(samples)

        # 区間ごとの内訳は合算して 1 つにまとめる。利用者が見るのは総和。
        for stage, seconds in output.stage_timings:
            timings[stage] = timings.get(stage, 0.0) + seconds
        for note in output.notes:
            if note not in notes:
                notes.append(note)

    notes.insert(0, f"info: 長いテキストを {len(outputs)} 区間に分けて合成しました。")

    return JoinedAudio(
        samples=audio_utils.concat_segments(pieces),
        sample_rate=sample_rate,
        used_seed=outputs[0].used_seed,
        stage_timings=sorted(timings.items(), key=lambda item: -item[1]),
        notes=notes,
    )
