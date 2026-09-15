"""合成した音のかんたんな解析。

話者を作る前に「どんな声になるか」の手がかりを出すために使う。見るのは声の高さ
（基本周波数）だけで、自己相関から求める。外部ライブラリは numpy しか要らない。

声の高さと性別・年齢は一対一ではない。ここで返すのはあくまで測った高さと、
その高さがどのあたりかという目安であって、話者の属性を決めつけるものではない。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 人の声の基本周波数が収まる範囲。ここから外れた相関のピークは拾わない。
PITCH_FLOOR_HZ = 70.0
PITCH_CEILING_HZ = 400.0

# 自己相関のピークがこれを下回るフレームは、周期が立っていない（無声）とみなす。
PERIODICITY_FLOOR = 0.3


@dataclass(frozen=True)
class PitchSummary:
    """測った声の高さ。"""

    median_hz: float
    """有声フレームの中央値。"""

    low_hz: float
    """下から 4 分の 1 の位置。抑揚の幅を見るために添える。"""

    high_hz: float
    """上から 4 分の 1 の位置。"""

    voiced_ratio: float
    """有声と判定したフレームの割合。低いほど測定が頼りない。"""

    label: str
    """高さの目安。"""

    note: str
    """目安の読み方。"""

    def to_dict(self) -> dict:
        return {
            "median_hz": round(self.median_hz, 1),
            "low_hz": round(self.low_hz, 1),
            "high_hz": round(self.high_hz, 1),
            "voiced_ratio": round(self.voiced_ratio, 3),
            "label": self.label,
            "note": self.note,
        }


def _describe(median_hz: float) -> tuple[str, str]:
    """測った高さに説明を添える。

    境界は成人の発話の一般的な分布から置いている。声の高さは性別とも年齢とも
    ずれることがあるため、断定する言い方は避ける。
    """

    if median_hz < 135:
        return ("低め", "成人男性の話し声によくある高さです。")
    if median_hz < 165:
        return ("やや低め", "男性の高めの声と、女性の低めの声が重なる範囲です。")
    if median_hz < 200:
        return ("中くらい", "男女どちらもとりうる高さです。声色での判断が要ります。")
    if median_hz < 260:
        return ("高め", "成人女性の話し声によくある高さです。")
    return ("かなり高め", "女性の高い声、または若い話者に寄った高さです。")


def estimate_pitch(samples: np.ndarray, sample_rate: int) -> PitchSummary | None:
    """自己相関で基本周波数を測る。有声フレームが足りなければ None を返す。"""

    if sample_rate <= 0 or samples.size == 0:
        return None

    mono = samples.astype(np.float64)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)

    frame = int(sample_rate * 0.04)
    hop = int(sample_rate * 0.02)
    min_lag = max(1, int(sample_rate / PITCH_CEILING_HZ))
    max_lag = int(sample_rate / PITCH_FLOOR_HZ)
    if mono.size < frame or max_lag <= min_lag:
        return None

    # 無音や息だけのフレームを外すための下限。全体の大きさから決める。
    overall = float(np.sqrt(np.mean(mono**2)))
    if overall <= 0:
        return None
    energy_floor = overall * 0.25

    values: list[float] = []
    total = 0
    for start in range(0, mono.size - frame, hop):
        total += 1
        window = mono[start : start + frame]
        if float(np.sqrt(np.mean(window**2))) < energy_floor:
            continue

        window = window - window.mean()
        correlation = np.correlate(window, window, mode="full")[frame - 1 :]
        if correlation[0] <= 0:
            continue
        correlation = correlation / correlation[0]

        segment = correlation[min_lag : min(max_lag, correlation.size)]
        if segment.size == 0:
            continue

        lag = int(np.argmax(segment)) + min_lag
        if correlation[lag] < PERIODICITY_FLOOR:
            continue
        values.append(sample_rate / lag)

    if total == 0 or len(values) < 5:
        return None

    array = np.asarray(values)
    median = float(np.median(array))
    label, note = _describe(median)
    return PitchSummary(
        median_hz=median,
        low_hz=float(np.percentile(array, 25)),
        high_hz=float(np.percentile(array, 75)),
        voiced_ratio=len(values) / total,
        label=label,
        note=note,
    )
