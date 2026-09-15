"""痩せた低域を、話者本来の厚みへ戻す。

感嘆詞だけが並ぶ行（「あっ、あん、…っ！」のような喘ぎ声や相槌）を合成すると、
モデルは息声として読み上げる。基音と低次倍音のエネルギーが落ち、1〜4kHz だけが
残るため、声が薄く AM ラジオのように聞こえる。

実測（同一シード 3 本の平均・有声部のみ・1kHz 未満が占める振幅の割合）:

    話者          普通の文   感嘆詞だけの行
    やわらか        52.4%        17.1%
    ミライ          34.2%        10.8%
    カコ            39.8%        10.5%

落ち込む比率は話者によらず約 0.3 倍で、テキストの書き方に由来する。steps を
8 から 32 へ上げても戻らない（やわらかで 17.1% → 14.8%）ため、サンプリング回数
では解決しない。参照音声そのものは 31〜38% あり、普通の文ではその値がほぼその
まま出る（ミライで参照 34.1% に対し合成 34.2%）ので、話者の写し取りでもない。

そこで合成後に一度だけローシェルフを当てて、不足している分を持ち上げる。足りて
いる行には何もしない。位相を回すと子音の立ち上がりが鈍るため、周波数領域で
ゲイン曲線を掛けるゼロ位相の実装にしている。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# スペクトルを見るときの窓。測定と補正で同じ値を使う。
_FRAME = 2048
_HOP = 512

# 声の土台とみなす帯域の上端。基音（70〜400Hz）とその低次倍音が入る。
_LOW_BAND_HZ = 1000.0

# 無音と息だけの区間を測定から外すための下限。最大フレームに対する比。
_VOICED_FLOOR = 0.10


@dataclass(frozen=True)
class LowBandPolicy:
    """低域を戻す条件。

    target_ratio は補正を始める境目であり、到達点ではない。シェルフは帯域全体を
    一様に持ち上げるわけではないので、実際の到達値は計算より下回る（ミライの
    感嘆詞の行で 13.6% → 20.6%）。同梱話者の普通の文が 52%、参照音声から写した
    話者が 34〜40% なので、その下限をさらに下回る 25% を境にしている。普通の文は
    この値を上回るため素通りする。

    shelf_hz と shelf_order は、低域だけを持ち上げて 1〜4kHz を動かさない形を
    実測で選んだ。1 次では 700Hz でも 1.2 倍にしかならず低域に届かず、3 次は
    効くがゼロ位相フィルタの前後に残るリンギングが伸びるため 2 次にしている。
    """

    enabled: bool = True
    target_ratio: float = 0.25
    max_gain_db: float = 8.0
    shelf_hz: float = 1000.0
    shelf_order: int = 2


@dataclass
class RestoredAudio:
    samples: np.ndarray
    # 実際に掛けたゲイン。0.0 なら何もしていない。
    applied_gain_db: float
    measured_ratio: float


def low_band_ratio(samples: np.ndarray, sample_rate: int) -> float:
    """声が出ている区間で、1kHz 未満が占める振幅の割合を返す。

    無音を含めて測ると、間の多い行ほど無音側へ引かれて値が濁る。エネルギーの
    ある区間だけを見る。
    """

    if samples.size < _FRAME or sample_rate <= 0:
        return 0.0

    window = np.hanning(_FRAME)
    freqs = np.fft.rfftfreq(_FRAME, d=1.0 / sample_rate)
    low = freqs < _LOW_BAND_HZ

    spectra: list[np.ndarray] = []
    energies: list[float] = []
    for start in range(0, samples.size - _FRAME, _HOP):
        frame = samples[start : start + _FRAME] * window
        energies.append(float(np.sqrt(np.mean(frame**2))))
        spectra.append(np.abs(np.fft.rfft(frame)))

    if not spectra:
        return 0.0

    energy_array = np.asarray(energies)
    peak = float(energy_array.max())
    if peak <= 0.0:
        return 0.0

    voiced = np.asarray(spectra)[energy_array >= peak * _VOICED_FLOOR]
    total = float(voiced.sum())
    if total <= 0.0:
        return 0.0
    return float(voiced[:, low].sum()) / total


def _required_gain(ratio: float, target: float) -> float:
    """低域の割合を target まで押し上げる線形ゲインを返す。

    低域を G 倍すると割合は GL / (GL + R) になる。これが target と等しくなる G は
    target/(1-target) × (1-ratio)/ratio。
    """

    return (target / (1.0 - target)) * ((1.0 - ratio) / ratio)


def _shelf_curve(
    freqs: np.ndarray, *, linear_gain: float, shelf_hz: float, order: int
) -> np.ndarray:
    """直流で linear_gain、shelf_hz で中間、高域で 1 に漸近するシェルフ。"""

    return 1.0 + (linear_gain - 1.0) / (1.0 + (freqs / shelf_hz) ** (2 * order))


def apply_low_band_restore(
    samples: np.ndarray,
    *,
    sample_rate: int,
    policy: LowBandPolicy = LowBandPolicy(),
) -> RestoredAudio:
    """低域が目標を下回っていれば持ち上げて返す。足りていればそのまま返す。"""

    source = samples.astype(np.float32, copy=False)
    if not policy.enabled or source.size < _FRAME or sample_rate <= 0:
        return RestoredAudio(samples=source, applied_gain_db=0.0, measured_ratio=0.0)

    ratio = low_band_ratio(source, sample_rate)
    if ratio <= 0.0 or ratio >= policy.target_ratio:
        return RestoredAudio(samples=source, applied_gain_db=0.0, measured_ratio=ratio)

    gain_db = min(20.0 * math.log10(_required_gain(ratio, policy.target_ratio)), policy.max_gain_db)
    if gain_db <= 0.0:
        return RestoredAudio(samples=source, applied_gain_db=0.0, measured_ratio=ratio)

    spectrum = np.fft.rfft(source.astype(np.float64))
    freqs = np.fft.rfftfreq(source.size, d=1.0 / sample_rate)
    curve = _shelf_curve(
        freqs,
        linear_gain=10.0 ** (gain_db / 20.0),
        shelf_hz=policy.shelf_hz,
        order=policy.shelf_order,
    )
    restored = np.fft.irfft(spectrum * curve, n=source.size)

    # 低域を足すと波形の振幅は必ず増える。原音のピークを超えた分だけ戻し、
    # 行ごとに音量が変わって聞こえるのを防ぐ。
    source_peak = float(np.max(np.abs(source)))
    restored_peak = float(np.max(np.abs(restored)))
    if restored_peak > source_peak > 0.0:
        restored = restored * (source_peak / restored_peak)

    return RestoredAudio(
        samples=np.ascontiguousarray(restored, dtype=np.float32),
        applied_gain_db=gain_db,
        measured_ratio=ratio,
    )
