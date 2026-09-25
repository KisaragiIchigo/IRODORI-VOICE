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

``BASE_SECONDS`` と ``SECONDS_PER_MORA`` は上表の借りた声 18 点の最小二乗で、本文から
見積もった自然な長さとして使う。

■ 予測を信用できる声（借りた声・自分で録った参照音声の声）

予測はほぼ自然な長さに収まるので、そのまま使い、走りすぎだけを止める。実測のばらつきは
式の最大 1.186 倍だったので、``MARGIN`` はそれを少しだけ上回る 1.25 倍に置く。

注釈絵文字は間の取り方そのものへの指示で、モーラ数からは読めない（🐢 と ⏩ では同じ文の
長さが 1.76 秒開く）。実測でも 7 モーラの ⏩ は借りた声で 2.48 秒まで伸びる。注釈がある
本文には ``ANNOTATED_MARGIN`` を使う。借りた声の 🐢 1.60 秒・⏩ 2.48 秒・😆 1.68 秒・
📖 1.52 秒を通したまま、シードの声の ⏩ 6.44 秒・4.32 秒と 📖 3.28 秒を抑えられる。

極端に短い本文では式そのものが小さくなりすぎるため、下限を置く。借りた声の最長は
「はい？」1.13 秒、「😮‍💨……ふぅ。」1.37 秒だった。

■ 予測を信用できない声（シードから作った声・参照音声を持たない声）

同梱話者を含むこれらの声は、短い本文の予測が自然な長さの 1.3〜3 倍に伸びる。キャプションで
表情を付けるとさらに伸びる（少年の「はい。」がキャプションなし 1.18 秒、朗読の指示で
2.28 秒）。予測は上限へ当たり、上限いっぱいの尺で鳴る。

そのため、倍率で余裕を持たせた上限では、余りがそのまま埋め草になる。利用者の聴取では、
上限 1.2 秒の「はい。」は正しく読めたが、同じ 1.2 秒の「うん。」は「えんちにー」「おーい」に
なった。1.44 秒の「……ふぅ。」は「いーーー」、1.8 秒の「😮‍💨……ふぅ。」は「ふううう」と
伸びた。短い行ほど自然な長さの差が大きく、余裕をどこに置いても必ずどこかで余る。

これらの声では、見積もった自然な長さそのものを上限にする（``UNTRUSTED_MARGIN``）。
注釈絵文字がある行だけ、ため息や間の分として 1.2 倍を残す。上限いっぱいで鳴るのが前提
なので、下限は置かない。

■ 両方に共通

三点リーダは読まずに間を置く指示で、モーラ数に表れない。1 か所につき ``PAUSE_SECONDS``
（README の実測で三点リーダが伸ばした 0.40 秒）を見積もりへ足す。借りた声の注釈がある行は
倍率と下限が既に広いので足さない。重ねると余りが増え、埋め草を招く。

話速とスタイルの倍率は上限にも掛ける。話速を落としたときに正当に伸びた分まで切らないため。
"""

from __future__ import annotations

import re

from ...vendor.irodori_tts.duration import count_annotation_emojis
from .word_boundaries import analyze

# 借りた声 18 点（2〜55 モーラ・ノーマル）の最小二乗。
BASE_SECONDS = 0.6085
SECONDS_PER_MORA = 0.1511

# 予測を信用できる声の倍率。実測のばらつきの上限（1.186 倍）をわずかに上回る値。
MARGIN = 1.25

# 同じく注釈絵文字がある本文への倍率。間の取り方が指示で変わるため広く取る。
ANNOTATED_MARGIN = 1.8

# 予測を信用できる声の下限。借りた声の「はい？」1.13 秒を切らない値。
MIN_CAP_SECONDS = 1.2

# 同じく注釈絵文字がある本文の下限。借りた声の「😮‍💨……ふぅ。」1.37 秒を切らない値。
ANNOTATED_MIN_CAP_SECONDS = 1.8

# 予測を信用できない声の倍率。見積もった自然な長さそのものを上限にする。
UNTRUSTED_MARGIN = 1.0

# 同じく注釈絵文字がある本文への倍率。ため息や間の分だけ残す。
UNTRUSTED_ANNOTATED_MARGIN = 1.2

# 三点リーダ 1 か所で見込む間。
PAUSE_SECONDS = 0.4

# Irodori-TTS の既定の上限。これを緩める方向へは動かさない。
ABSOLUTE_MAX_SECONDS = 30.0

# 拗音は直前の仮名と合わせて 1 モーラになる。長音・促音・撥音はそれぞれ 1 モーラ。
_SMALL_KANA = frozenset("ァィゥェォャュョヮ")

# 連なった三点リーダはまとめて 1 か所と数える。半角ピリオドの連続は上流で「…」へ変わる。
_PAUSE = re.compile(r"[…‥⋯]+|\.{2,}")


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


def resolve_max_seconds(
    text: str, *, duration_scale: float, trust_prediction: bool = True
) -> float | None:
    """この本文に許す尺の上限を秒で返す。決められないときは ``None``。

    ``duration_scale`` は話速とスタイルの指定をまとめた倍率で、予測フレーム数へ掛かるのと
    同じ値を渡す。上限も同じ空間に置かないと、話速を落としたときに正当に伸びた分まで
    切ってしまう。``trust_prediction`` は話者の予測が自然な長さに収まるかどうか。
    """

    count = count_morae(text)
    if count is None or count <= 0:
        return None

    annotated = bool(count_annotation_emojis(text))
    pauses = len(_PAUSE.findall(text))
    if trust_prediction:
        margin = ANNOTATED_MARGIN if annotated else MARGIN
        floor = ANNOTATED_MIN_CAP_SECONDS if annotated else MIN_CAP_SECONDS
        if annotated:
            pauses = 0
    else:
        margin = UNTRUSTED_ANNOTATED_MARGIN if annotated else UNTRUSTED_MARGIN
        floor = 0.0
    estimate = BASE_SECONDS + SECONDS_PER_MORA * count + PAUSE_SECONDS * pauses
    cap = max(estimate * margin, floor) * max(float(duration_scale), 0.0)
    return min(cap, ABSOLUTE_MAX_SECONDS)
