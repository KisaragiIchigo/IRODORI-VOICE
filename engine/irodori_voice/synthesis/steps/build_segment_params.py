"""区間ごとの合成パラメータを組み立てる。

分割した区間は「同じ声で、同じ調子で」読まれなければならない。
そのためシードとスタイル指定は全区間で共有し、前後の無音だけを区間ごとに変える。
"""

from __future__ import annotations

from ...backends.base import SynthesisParams
from .split_text import TextSegment


def build_segment_params(
    base: SynthesisParams,
    segment: TextSegment,
    *,
    seed: int,
    total_segments: int,
) -> SynthesisParams:
    """1 区間ぶんのパラメータを作る。

    前の無音は最初の区間だけ、後ろの無音は最後の区間だけ元の指定を使う。
    中間の区間には区切りに応じた無音を入れ、連結したときの間を整える。
    """

    is_first = segment.index == 0
    is_last = segment.index == total_segments - 1

    return SynthesisParams(
        text=segment.text,
        voice_id=base.voice_id,
        style_id=base.style_id,
        speed=base.speed,
        volume=base.volume,
        pitch=base.pitch,
        intonation=base.intonation,
        # 区間の境目で元の前後無音を繰り返すと、間が不自然に伸びる。
        pre_silence=base.pre_silence if is_first else 0.0,
        post_silence=base.post_silence if is_last else segment.trailing_silence,
        caption=base.caption,
        style_strength=base.style_strength,
        # 全区間で同じシードを使う。ここが揺れると区間ごとに別人になる。
        seed=seed,
        steps=base.steps,
    )
