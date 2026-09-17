"""指定された話速を、間と声へ配り直す。

全体の長さは指定どおりに変える。変えるのは内訳で、文の切れ目の間を指定より強く
詰め、その分だけ声の側を緩める。1.5 倍の指定なら声は 1.38 倍あたりになる
（間が全体の 16% を占める行で実測）。

詰める相手は長い間だけに絞る。読点ほどの短い間まで同じ比率で詰めると文節が
くっついて聞き取れなくなるため、短い間は声と同じ扱いにする。

配り方は速める側と緩める側で対称。ゆっくり読ませるときも、人は声を伸ばす前に
間を伸ばす。
"""

from __future__ import annotations

from dataclasses import dataclass

from .detect_pause_spans import PauseSpan

# 指定された速度の変化を、声の側が引き受ける割合。残りは長い間が負担する。
# 1.0 にすると全体が同じ比率で縮み、いまの早回し感に戻る。0 に近づけるほど
# 声の長さは変わらなくなるが、間だけが極端に詰まって落語のような間合いになる。
_SPEECH_SHARE = 0.72

# 詰める対象にする間の長さ。日本語の読点の間が 150〜250ms、句点の間が
# 400〜700ms。ここを下回る間は文節の区切りそのものなので、声と同じ倍率で扱う。
_LONG_PAUSE_SECONDS = 0.180

# 長い間に許す倍率の上限。0.7 秒の間が 0.18 秒まで詰まる幅。これを超えて詰めると
# 文の切れ目が消えて一息で読んだように聞こえる。緩める側にも同じ幅で効く。
_PAUSE_LIMIT = 4.0


@dataclass(frozen=True)
class SpeedBlock:
    """ひと続きに同じ倍率を当てる区間。サンプル番号の半開区間 [start, end)。"""

    start: int
    end: int
    factor: float


@dataclass(frozen=True)
class SpeedPlan:
    """波形をどう伸縮するかの計画。"""

    blocks: tuple[SpeedBlock, ...]
    speech_factor: float
    pause_factor: float


def _solve_factors(*, pause_samples: int, speech_samples: int, scale: float) -> tuple[float, float]:
    """声と間の倍率を、全体の長さが 1/scale になるように解く。

    声を ks 倍・間を kp 倍にしたときの長さは Ts/ks + Tp/kp。狙いの長さ T/scale と
    等しくなる kp は Tp / (T/scale - Ts/ks) で求まる。
    """

    total = pause_samples + speech_samples
    target = total / scale

    speech_factor = 1.0 + (scale - 1.0) * _SPEECH_SHARE
    pause_room = target - speech_samples / speech_factor

    lower, upper = 1.0 / _PAUSE_LIMIT, _PAUSE_LIMIT
    if pause_room <= pause_samples / upper:
        pause_factor = upper
    elif pause_room >= pause_samples / lower:
        pause_factor = lower
    else:
        return speech_factor, pause_samples / pause_room

    # 間だけでは足りなかった分を声へ戻す。間が短い行では scale そのものに近づき、
    # 一様に伸縮していたときと同じ結果になる。
    speech_room = target - pause_samples / pause_factor
    if speech_room <= 0.0:
        return scale, scale
    return speech_samples / speech_room, pause_factor


def _merge_adjacent(blocks: list[SpeedBlock]) -> tuple[SpeedBlock, ...]:
    """同じ倍率で隣り合う区間をひとつにする。

    短い間は声と同じ倍率になるため、繋げてしまえば伸縮の回数も継ぎ目も減る。
    """

    merged: list[SpeedBlock] = []
    for block in blocks:
        previous = merged[-1] if merged else None
        if previous is not None and previous.factor == block.factor:
            merged[-1] = SpeedBlock(start=previous.start, end=block.end, factor=block.factor)
        else:
            merged.append(block)
    return tuple(merged)


def build_speed_plan(
    pauses: list[PauseSpan], *, total_samples: int, sample_rate: int, scale: float
) -> SpeedPlan:
    """間の位置から、区間ごとの倍率を決める。"""

    threshold = int(_LONG_PAUSE_SECONDS * sample_rate)
    long_pauses = [span for span in pauses if span.length >= threshold]

    pause_samples = sum(span.length for span in long_pauses)
    speech_samples = total_samples - pause_samples

    if pause_samples <= 0 or speech_samples <= 0:
        speech_factor = pause_factor = scale
    else:
        speech_factor, pause_factor = _solve_factors(
            pause_samples=pause_samples, speech_samples=speech_samples, scale=scale
        )

    blocks: list[SpeedBlock] = []
    cursor = 0
    for span in long_pauses:
        if span.start > cursor:
            blocks.append(SpeedBlock(start=cursor, end=span.start, factor=speech_factor))
        blocks.append(SpeedBlock(start=span.start, end=span.end, factor=pause_factor))
        cursor = span.end
    if cursor < total_samples:
        blocks.append(SpeedBlock(start=cursor, end=total_samples, factor=speech_factor))

    return SpeedPlan(
        blocks=_merge_adjacent(blocks),
        speech_factor=speech_factor,
        pause_factor=pause_factor,
    )
