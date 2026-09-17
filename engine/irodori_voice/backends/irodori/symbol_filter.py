"""読みの無い記号を、モデルへ渡すテキストから落とす。

Irodori-TTS は表記から直接音を作るモデルで、本文に置かれた「※」や「：」のような
飾りの記号も読み上げの対象になる。OpenJTalk はこれらに読みを与えず（アクセント句の
表示にも現れない）、エディタの画面では読まれないように見えるため、音だけが画面と
食い違う。ここで落として、表示と音を揃える。

落とす記号は解析結果から決める。文字ごとに決め打ちにできないのは、同じ記号でも
前後で読まれたり読まれなかったりするため。「％」は数字に続けば「パーセント」と読まれ、
単独では読まれない。「＆」も「アンド」と読まれる場面がある。読みを持つ記号は残す。

辞書に登録した記号は、この層へ来る前に ``reading_overrides`` が読みへ置き換えている。
登録すれば読ませられる、というのがここでの約束。
"""

from __future__ import annotations

from ...vendor.irodori_tts.duration import ALLOWED_ANNOTATION_EMOJIS
from .word_boundaries import analyze

# 解析が「読みなし」を表すのに使う値。OpenJTalk は読まない記号の読みを読点で埋める。
_NO_READING = frozenset({"", "*", "、"})

# 読みが無くても本文へ残す文字。
#   * 句読点と三点リーダ、感嘆・疑問符は間と抑揚の材料になる
#   * 括弧と引用符は、その中の言い回しを語り分ける手がかりになる
#   * 注釈絵文字はモデルへの指示そのもので、読み上げの対象ではない
#   * 度の記号は単位の一部。NFKC が「℃」を「°」と「C」へ分解するため、落とすと
#     「25℃」が「25C」になって読みが変わる
_KEEP = frozenset(
    "、。，．,.…‥！？!?「」『』（）()【】〔〕［］[]｛｝{}〈〉《》°"
) | frozenset("".join(ALLOWED_ANNOTATION_EMOJIS))


def drop_unreadable_symbols(text: str) -> str:
    """読みの無い記号を落とす。解析が使えないときは本文をそのまま返す。"""

    spans = analyze(text)
    if spans is None:
        return text

    kept: list[str] = []
    for span in spans:
        piece = text[span.start : span.end]
        if span.pron is None or span.pron.strip() not in _NO_READING:
            kept.append(piece)
            continue
        kept.append("".join(char for char in piece if char in _KEEP))

    filtered = "".join(kept)
    # 記号だけの行はここで空になる。モデルへ空文字を渡すと合成が立たないため、
    # そのときは落とさずに渡し、上位の無音応答へ判断を委ねる。
    return filtered if filtered.strip() else text
