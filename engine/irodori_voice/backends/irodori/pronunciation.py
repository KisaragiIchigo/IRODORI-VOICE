"""漢字を含む語の読みを、Irodoriへ渡す本文に明示する。

Irodori-TTS は表記からそのまま音を作るモデルで、読み仮名を受け取る口がない。
漢字の読みを直す手段は表記の書き換えしかないが、書き換えた表記はモデルにとって
学習時と違う見た目になり、アクセントの置きどころが崩れる。

とくに OpenJTalk の読みは長音を「ー」で表すため、素朴に仮名へ直すと「設定画面から
生成回数を変更できます」が「せってーがめんからせーせーかいすーをへんこーできます」
になる。日本語の文章に現れない綴りで、語の切れ目もアクセント核の手がかりも消える。
ここでは長音を母音へ開いて「せっていがめんからせいせいかいすうをへんこうできます」
の形まで戻し、崩れの幅を抑える。

それでも元の漢字表記ほどの手がかりは戻らない。この変換を掛けるかどうかは
``EngineSettings.pronunciation_mode`` が決め、既定では掛けない。
"""

from __future__ import annotations

import re

from .word_boundaries import analyze

_KANJI = re.compile(r"[々〆〇\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]")
_KANA = re.compile(r"[ァ-ヶー]+")
_KANA_TO_HIRA = str.maketrans({chr(code): chr(code - 0x60) for code in range(0x30A1, 0x30F7)})

# 仮名が持つ母音。長音記号を開くときに、直前の仮名から引く。
_VOWEL_GROUPS = {
    "a": "あかさたなはまやらわがざだばぱゃぁゎ",
    "i": "いきしちにひみりぎじぢびぴぃ",
    "u": "うくすつぬふむゆるぐずづぶぷゅぅ",
    "e": "えけせてねへめれげぜでべぺぇ",
    "o": "おこそとのほもよろをごぞどぼぽょぉ",
}
_VOWEL_OF = {kana: vowel for vowel, kanas in _VOWEL_GROUPS.items() for kana in kanas}

# 長音記号を置き換える仮名。エ段とオ段は、漢字語の長音の大半を占める音読みに合わせる
# （「せってー」は「せってい」、「へんこー」は「へんこう」）。訓読みのオ段長音だけは
# 「とおる」が「とうる」になるが、音は変わらず、綴りとしては「とーる」より通る。
_LONG_VOWEL_KANA = {"a": "あ", "i": "い", "u": "う", "e": "い", "o": "う"}


def to_hiragana(text: str) -> str:
    return text.translate(_KANA_TO_HIRA)


def expand_long_vowels(kana: str) -> str:
    """ひらがなに残った長音記号を、直前の仮名の母音へ開く。

    直前が「ん」「っ」など母音を持たない仮名のときは、開く先が決まらないので
    長音記号のまま残す。
    """

    expanded: list[str] = []
    for char in kana:
        if char != "ー":
            expanded.append(char)
            continue
        previous = expanded[-1] if expanded else ""
        vowel = _VOWEL_OF.get(previous)
        expanded.append(_LONG_VOWEL_KANA[vowel] if vowel else char)
    return "".join(expanded)


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
            parts.append(expand_long_vowels(to_hiragana(pronunciation)))
        else:
            parts.append(piece)
    return "".join(parts)
