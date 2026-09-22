"""本文の長さから、読み上げに許す尺の上限を決める。

Irodori-TTS は読み上げる長さを先に予測し、そのフレーム数を最後まで埋める。自己回帰では
ないため「読み終わったから止まる」ができない。予測が本文より長いと、モデルは余った尺を
埋めるしかなく、冒頭へ破裂音を置いたり、本文に無い語を足したり、同じ句をもう一度読んだり
する。

外れるのは短い本文だけで、長い本文では話者によらず予測が揃う。実測（同じ本文・同じ条件・
ノーマル）:

    モーラ   借りた声 3 人の尺     シードの声 3 人の尺
      2     0.80〜1.08 秒        3.36〜4.00 秒
      6     1.36〜1.48 秒        3.16〜3.92 秒
      7     1.56〜1.72 秒        2.72〜3.32 秒
     11     2.20〜2.40 秒        3.48〜3.88 秒
     32     5.56〜5.64 秒        5.04〜5.44 秒
     55     8.76〜8.92 秒        8.24〜8.80 秒

シードの声には 3 秒前後の底があり、本文がいくら短くてもそこまでしか縮まない。32 モーラ
以上では借りた声と揃うため、壊れているのは予測器そのものではなく、短い本文に対する
振る舞いだけになる。

``BASE_SECONDS`` と ``SECONDS_PER_MORA`` は上表の借りた声 18 点の最小二乗。実測のばらつきは
式の最大 1.186 倍だったので、余裕を見て ``MARGIN`` を 1.4 倍に置く。この上限なら借りた声・
同梱話者・話速 0.5 のいずれも切らず、シードの声の外れ値 12 件すべてを抑えられる。

注釈絵文字は間の取り方そのものへの指示で、モーラ数からは読めない（🐢 と ⏩ では同じ文の
長さが 1.76 秒開く）。実測でも 7 モーラの ⏩ は借りた声で 2.48 秒まで伸び、ノーマル用の
上限では切れてしまう。注釈がある本文には ``ANNOTATED_MARGIN`` を使う。7 モーラで 3.00 秒
となり、借りた声の 🐢 1.60 秒・⏩ 2.48 秒・😆 1.68 秒・📖 1.52 秒を通したまま、シードの声の
⏩ 6.44 秒・4.32 秒と 📖 3.28 秒を抑えられる。

極端に短い本文では式そのものが小さくなりすぎる。2 モーラの「はい。」は式が 0.91 秒、
1.4 倍でも 1.27 秒だが、同梱のナレーションは 1.32 秒を必要とした。そのため
``MIN_CAP_SECONDS`` を別に置く。

予測器は使ったままで、走りすぎだけを止める。上限に当たらない限り出力は変わらない。
"""

from __future__ import annotations

from ...vendor.irodori_tts.duration import count_annotation_emojis
from .word_boundaries import analyze

# 借りた声 18 点（2〜55 モーラ・ノーマル）の最小二乗。
BASE_SECONDS = 0.6085
SECONDS_PER_MORA = 0.1511

# 式に対して許す倍率。実測のばらつきの上限（1.186 倍）に余裕を足した値。
MARGIN = 1.4

# 注釈絵文字がある本文へ使う倍率。間の取り方が指示で変わるため広く取る。
ANNOTATED_MARGIN = 1.8

# 極端に短い本文で式が小さくなりすぎるのを防ぐ下限。
MIN_CAP_SECONDS = 1.8

# Irodori-TTS の既定の上限。これを緩める方向へは動かさない。
ABSOLUTE_MAX_SECONDS = 30.0

# 拗音は直前の仮名と合わせて 1 モーラになる。長音・促音・撥音はそれぞれ 1 モーラ。
_SMALL_KANA = frozenset("ァィゥェォャュョヮ")


def _is_mora(char: str) -> bool:
    if char in _SMALL_KANA:
        return False
    return char == "ー" or "ァ" <= char <= "ヶ"


def count_morae(text: str) -> int | None:
    """本文のモーラ数を返す。OpenJTalk が使えないときは ``None``。"""

    spans = analyze(text)
    if spans is None:
        return None

    reading = "".join(span.pron or "" for span in spans)
    return sum(1 for char in reading if _is_mora(char))


def resolve_max_seconds(text: str, *, duration_scale: float) -> float | None:
    """この本文に許す尺の上限を秒で返す。決められないときは ``None``。

    ``duration_scale`` は話速とスタイルの指定をまとめた倍率で、予測フレーム数へ掛かるのと
    同じ値を渡す。上限も同じ空間に置かないと、話速を落としたときに正当に伸びた分まで
    切ってしまう。
    """

    count = count_morae(text)
    if count is None or count <= 0:
        return None

    margin = ANNOTATED_MARGIN if count_annotation_emojis(text) else MARGIN
    estimate = BASE_SECONDS + SECONDS_PER_MORA * count
    cap = max(estimate * margin, MIN_CAP_SECONDS) * max(float(duration_scale), 0.0)
    return min(cap, ABSOLUTE_MAX_SECONDS)
