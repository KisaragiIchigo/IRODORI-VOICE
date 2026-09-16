"""合成済みの波形を、要求された話速へ伸縮する。

モデルへは常に 1.0 倍で喋らせ、速度の指定はここで当てる。Irodori-TTS へ直接
早口を指示すると生成そのものが崩れ、言葉として聞き取れない行が出る。声質が最も
安定する速度で作ってから位相ボコーダで伸ばし縮めた方が、どの速度域でも音が保てる。

伸縮は音高を変えない。話速だけが変わる。
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from pedalboard import time_stretch

# この幅に収まる指定は等倍として扱う。聞き分けられない差のために、
# 位相ボコーダを通して音を作り直す意味がない。
SPEED_EPSILON = 0.01


def apply_speed_scale(wav: bytes, *, scale: float) -> bytes:
    """wav を ``scale`` 倍の速さへ伸縮して返す。等倍ならそのまま返す。"""

    if abs(scale - 1.0) <= SPEED_EPSILON:
        return wav

    with io.BytesIO(wav) as source:
        samples, sample_rate = sf.read(source)

    # pedalboard は (チャンネル, サンプル) で受け取る。soundfile が返すのは逆向き。
    channels = samples.astype(np.float32)
    channels = channels[None, :] if channels.ndim == 1 else channels.T

    stretched = time_stretch(
        channels,
        sample_rate,
        stretch_factor=scale,
        high_quality=True,
        transient_mode="smooth",
        transient_detector="soft",
        use_time_domain_smoothing=True,
        use_long_fft_window=False,
    )

    with io.BytesIO() as sink:
        sf.write(sink, stretched.T, sample_rate, format="WAV", subtype="PCM_16")
        return sink.getvalue()
