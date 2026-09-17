"""漢字を含む語の読みを、Irodoriへ渡す本文に明示する。"""

from __future__ import annotations

import re

from .word_boundaries import analyze

_KANJI = re.compile(r"[々〆〇\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]")
_KANA = re.compile(r"[ァ-ヶー]+")
_KANA_TO_HIRA = str.maketrans({chr(code): chr(code - 0x60) for code in range(0x30A1, 0x30F7)})


def to_hiragana(text: str) -> str:
    return text.translate(_KANA_TO_HIRA)


def apply_pronunciation(text: str) -> str:
    """解析できた漢字語だけを読みに替え、注釈・句読点・既存の仮名を保つ。"""
    if not _KANJI.search(text):
        return text
    spans = analyze(text)
    if spans is None:
        return text

    parts: list[str] = []
    for span in spans:
        piece = text[span.start:span.end]
        # OpenJTalkの無声化記号は、読み上げ本文の文字ではない。
        pronunciation = (span.pron or "").replace("’", "")
        if _KANJI.search(piece) and _KANA.fullmatch(pronunciation):
            parts.append(to_hiragana(pronunciation))
        else:
            parts.append(piece)
    return "".join(parts)
