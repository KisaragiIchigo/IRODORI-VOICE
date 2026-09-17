"""計画どおりに区間を伸縮して、1 本の波形へ戻す。

区間の境目は必ず間の中にある。間の振幅は本文の 1/50 以下（実測では継ぎ目の
サンプル差が 0.003 に対し、本文の隣接サンプル差は 0.18〜0.43）なので、位相が
合わなくてもクリックにはならない。区間ごとに一定の倍率で渡せるため、出力の
長さは指定した速度どおりに収まる。

倍率を配列で渡して 1 回で伸縮する道もあるが、pedalboard は配列を渡すと内部で
音を細かく切って処理するため、出力が狙いより 1.0〜1.3% 長くなる。話速は数値で
指定するものなので、そのずれは受け入れられない。
"""

from __future__ import annotations

import numpy as np
from pedalboard import time_stretch

from .build_speed_plan import SpeedPlan

# この幅に収まる倍率は等倍として素通しする。位相ボコーダを通すたびに音は
# わずかに痩せるため、聞き分けられない差のために通す意味がない。
_UNITY_EPSILON = 0.005

# Rubberband の設定。high_quality=True は R3 エンジンを選ぶ。
#
#   - transient_mode / transient_detector / use_time_domain_smoothing は R2
#     専用で、R3 では渡しても無視される（実測: smooth/soft/有効の組と既定の組で
#     出力が 1 サンプルも違わない）。声向けの調整として指定しても効かない。
#   - use_long_fft_window=False は R3 でも効くが、3kHz 以上を 1.5〜2.7dB 削る
#     （1.3〜2.0 倍で実測）。こもって聞こえるため既定（None）に任せる。
#   - preserve_formants は音高を動かさない今の使い方では働かないが、将来
#     pitch_shift_in_semitones を併用したときに声色が動かないよう有効にしておく。
_STRETCH_OPTIONS = dict(high_quality=True, preserve_formants=True)


def render_speed_plan(channels: np.ndarray, *, sample_rate: int, plan: SpeedPlan) -> np.ndarray:
    """(チャンネル, サンプル) の波形を、計画の倍率で伸縮して返す。"""

    pieces: list[np.ndarray] = []
    for block in plan.blocks:
        chunk = channels[:, block.start : block.end]
        if abs(block.factor - 1.0) <= _UNITY_EPSILON:
            pieces.append(chunk)
            continue
        pieces.append(
            time_stretch(chunk, sample_rate, stretch_factor=block.factor, **_STRETCH_OPTIONS)
        )

    return np.concatenate(pieces, axis=1)
