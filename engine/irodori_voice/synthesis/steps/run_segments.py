"""区間を順に合成する。

GPU は 1 本しかない前提でバックエンド側が直列化しているため、ここでは
並列化を試みない。区間ごとの結果はキャッシュに乗るので、同じ文を含む
別の行を合成するときには再利用される。
"""

from __future__ import annotations

from collections.abc import Callable

from ...backends.base import SynthesisOutput, SynthesisParams

# 区間ごとに呼ばれる合成関数。キャッシュ判定を含む実体は呼び出し側が渡す。
SegmentSynthesizer = Callable[[SynthesisParams], tuple[SynthesisOutput, bool]]


def run_segments(
    params_list: list[SynthesisParams],
    synthesize: SegmentSynthesizer,
) -> tuple[list[SynthesisOutput], bool]:
    """各区間を合成し、(結果, 全区間がキャッシュ命中だったか) を返す。

    1 区間でも実際に合成したなら、全体としてはキャッシュ命中ではないと扱う。
    """

    outputs: list[SynthesisOutput] = []
    all_cached = True

    for params in params_list:
        output, cached = synthesize(params)
        outputs.append(output)
        if not cached:
            all_cached = False

    return outputs, all_cached
