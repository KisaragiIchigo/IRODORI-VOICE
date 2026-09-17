"""波形から、読み上げの間（ポーズ）を見つける。

話速を上げたときの「早回し」感は、間と声を同じ比率で詰めることから来る。人が
速く話すときに最も縮むのは間であって、母音や子音の長さはそこまで変わらない。
テープを速く回すと全部が同じ比率で縮むので、あの独特の不自然さが出る。

そこで先に間の位置を押さえる。ここは位置を返すだけで、どれだけ詰めるかは
build_speed_plan が決める。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 音量を測る窓。日本語の短母音が 60〜100ms なので、それより細かく刻む。
_FRAME_SECONDS = 0.010
_HOP_SECONDS = 0.005

# 間とみなす音量の境目。行の最大音量からの相対値と、絶対値の下限の高い方を使う。
# 相対値だけでは小声の行で本文まで間に見え、絶対値だけでは大声の行で息継ぎを
# 拾えない。
_RELATIVE_FLOOR_DB = -38.0
_ABSOLUTE_FLOOR_DB = -55.0

# これより短い静けさは間として扱わない。破裂音（「か」「た」「ぱ」）の前には
# 20〜60ms の閉鎖区間があり、ここを詰めると子音が消えて別の音に聞こえる。
_MIN_PAUSE_SECONDS = 0.100

# 間の両端を、声の側へ返す幅。子音の立ち上がりと語尾の減衰は静けさの側へ
# はみ出しているため、境目をそのまま使うと語頭と語尾を削ることになる。
_EDGE_KEEP_SECONDS = 0.020


@dataclass(frozen=True)
class PauseSpan:
    """間の位置。サンプル番号の半開区間 [start, end)。"""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def _frame_levels(samples: np.ndarray, frame: int, hop: int) -> np.ndarray:
    """窓ごとの音量を dB で返す。

    窓を並べた二次元配列を作ると、長い行でエネルギーの写しが何百 MB にもなる。
    二乗の累積和を一度作れば、どの窓の合計も引き算 1 回で取れる。
    """

    cumulative = np.concatenate(([0.0], np.cumsum(np.square(samples, dtype=np.float64))))
    starts = np.arange(1 + (samples.size - frame) // hop) * hop
    rms = np.sqrt((cumulative[starts + frame] - cumulative[starts]) / frame)
    return 20.0 * np.log10(rms + 1e-12)


def _quiet_runs(quiet: np.ndarray) -> list[tuple[int, int]]:
    """True が連続する区間を窓番号の半開区間で返す。"""

    if not quiet.any():
        return []

    edges = np.diff(np.concatenate(([False], quiet, [False])).astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def detect_pause_spans(samples: np.ndarray, *, sample_rate: int) -> list[PauseSpan]:
    """静けさが続く区間を、前後の音を削らない位置まで狭めて返す。

    samples はモノラルの 1 次元配列。前後の無音（prePhonemeLength /
    postPhonemeLength）もここで間として拾う。話速を上げたときにそこだけ元の
    長さで残ると、読み始めと読み終わりが間延びして聞こえる。
    """

    frame = int(_FRAME_SECONDS * sample_rate)
    hop = int(_HOP_SECONDS * sample_rate)
    if sample_rate <= 0 or frame <= 0 or samples.size < frame:
        return []

    levels = _frame_levels(samples, frame, hop)
    floor_db = max(float(levels.max()) + _RELATIVE_FLOOR_DB, _ABSOLUTE_FLOOR_DB)

    minimum = int(_MIN_PAUSE_SECONDS * sample_rate)
    keep = int(_EDGE_KEEP_SECONDS * sample_rate)

    spans: list[PauseSpan] = []
    for first, last in _quiet_runs(levels < floor_db):
        start = first * hop
        end = min(samples.size, (last - 1) * hop + frame)

        # 波形の端に接している側は削らない。そこに守るべき声はない。
        if start > 0:
            start += keep
        if end < samples.size:
            end -= keep

        if end - start >= minimum:
            spans.append(PauseSpan(start=start, end=end))

    return spans
