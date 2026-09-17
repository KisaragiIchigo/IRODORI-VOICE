"""合成済みの波形を、要求された話速へ伸縮する。

モデルへは常に 1.0 倍で喋らせ、速度の指定はここで当てる。Irodori-TTS へ直接
早口を指示すると生成そのものが崩れ、言葉として聞き取れない行が出る。声質が最も
安定する速度で作ってから位相ボコーダで伸ばし縮めた方が、どの速度域でも音が保てる。

ただし全体を同じ比率で縮めると、テープの早回しと同じことになる。人が速く話す
ときに縮むのはまず間であって、母音や子音の長さはそこまで変わらない。そこで間を
見つけ、指定より強く間を詰めて、その分だけ声の側を緩める。全体の長さは指定
どおりのままで、声の伸縮だけが浅くなる。

伸縮は音高を変えない。話速だけが変わる。

    波形
      │  detect_pause_spans   間の位置を見つける
      ▼
    間の一覧
      │  build_speed_plan     間と声へ倍率を配る
      ▼
    区間ごとの倍率
      │  render_speed_plan    区間ごとに伸縮して繋ぐ
      ▼
    話速の変わった波形
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

from .speed import build_speed_plan, detect_pause_spans, render_speed_plan

# この幅に収まる指定は等倍として扱う。聞き分けられない差のために、
# 位相ボコーダを通して音を作り直す意味がない。
SPEED_EPSILON = 0.01


def apply_speed_scale(wav: bytes, *, scale: float) -> bytes:
    """wav を ``scale`` 倍の速さへ伸縮して返す。等倍ならそのまま返す。"""

    if abs(scale - 1.0) <= SPEED_EPSILON:
        return wav

    with io.BytesIO(wav) as source:
        samples, sample_rate = sf.read(source, dtype="float32")

    # pedalboard は (チャンネル, サンプル) で受け取る。soundfile が返すのは逆向き。
    channels = samples[None, :] if samples.ndim == 1 else samples.T
    channels = np.ascontiguousarray(channels)

    # 間の判定はチャンネルを混ぜた 1 本で行う。左右で別々に間を取ると、
    # 区間の切れ目がずれて像が動く。
    mono = channels[0] if channels.shape[0] == 1 else channels.mean(axis=0)

    plan = build_speed_plan(
        detect_pause_spans(mono, sample_rate=sample_rate),
        total_samples=channels.shape[1],
        sample_rate=sample_rate,
        scale=scale,
    )
    stretched = render_speed_plan(channels, sample_rate=sample_rate, plan=plan)

    with io.BytesIO() as sink:
        sf.write(sink, stretched.T, sample_rate, format="WAV", subtype="PCM_16")
        return sink.getvalue()
