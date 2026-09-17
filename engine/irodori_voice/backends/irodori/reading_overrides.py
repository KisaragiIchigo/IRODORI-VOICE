"""ユーザー辞書の登録語を、モデルへ渡すテキストの上で置き換える。

Irodori-TTS は ``SamplingRequest.text`` の表記から直接音を作るモデルで、読み仮名を
受け取る口を持たない。そのため OpenJTalk のユーザー辞書は Irodori 話者の発音に
届かず（AIVM 話者には ``.dic`` 経由で効く）、読みを直す手段が表記の書き換えしか
ない。

実測でも、表記の違いがそのまま発音の成否になる。同じ話者・同じ設定で「楽天モバイル」
と書くと別の語に化けるが、「ラクテン」と書けば正しく読まれる。この差を利用者が
本文へ手で書き込まずに済むよう、辞書の登録語をここで当てる。

当てるのは語の切れ目に限る。語の途中で当てると別の語が壊れるためで、たとえば
「ＧＵＩ」を登録すると表記は「グイ」で保存され（AivisSpeech の辞書もこの形）、
素朴に置き換えると「ログイン」が「ロじいゆうあいン」へ化ける。切れ目は
``word_boundaries`` が形態素解析から読む。解析が使えないときだけ、仮名・英字・数字が
区切り記号なしで連なる性質を手がかりにした簡易判定へ落とす。

本文は左から 1 度だけ走査し、長い表記を先に試す。置き換えた読みの上をもう一度
走らないため、挿入した読みの中へ別の登録語が当たることがない。
"""

from __future__ import annotations

import re
import unicodedata

from .word_boundaries import token_boundaries

_KANA_TO_HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポァィゥェォャュョッヴ",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっゔ"
)

# 区切り記号なしで連なって 1 語を成す文字種。形態素解析が使えないときの簡易判定で、
# 表記の端がこの文字種なら、同じ文字種が隣にある一致を語の途中とみなす。漢字と
# ひらがなは入れない。「楽天」を「楽天市場」の中でも読ませたいように、語の一部でも
# 当てたい登録が多いため。
_RUN_CLASSES = (
    "ァ-ヺー",  # カタカナ。小書きと長音を含む
    "A-Za-z",  # 英字。NFKC 済みなので半角だけを見れば足りる
    "0-9",
)


def _run_class_of(char: str) -> str | None:
    """文字が属する連なりの文字種を返す。どれでもなければ ``None``。"""

    for chars in _RUN_CLASSES:
        if re.match(f"[{chars}]", char):
            return chars
    return None


def _is_run_boundary(text: str, start: int, end: int, surface: str) -> bool:
    """簡易判定。一致が同じ文字種の連なりの途中なら ``False``。"""

    head = _run_class_of(surface[0])
    if head and start > 0 and re.match(f"[{head}]", text[start - 1]):
        return False
    tail = _run_class_of(surface[-1])
    if tail and end < len(text) and re.match(f"[{tail}]", text[end]):
        return False
    return True


def _prepare(overrides: list[tuple[str, str]]) -> list[tuple[re.Pattern[str], str, str]]:
    """登録語を照合に使える形へ整える。長い表記から順に並べる。

    長い表記を先に試すのは、「楽天」と「楽天ペイ」の両方が登録されたときに短い方が
    先に当たって残りが崩れるのを避けるため。並び順は NFKC を通したあとの長さで
    決め直す。全角の英数字は半角へ畳まれて長さが変わりうる。
    """

    prepared: list[tuple[re.Pattern[str], str, str]] = []
    for surface, pronunciation in overrides:
        surface_nfkc = unicodedata.normalize("NFKC", surface)
        if not surface_nfkc:
            continue
        # VOICEVOXエディタは辞書の「読み」をカタカナで強制するが、
        # Irodori-TTSにカタカナをそのまま渡すと外来語のような不自然なイントネーションになる。
        # そこで、置換前にカタカナをひらがなへ変換する。
        pronunciation_hira = pronunciation.translate(_KANA_TO_HIRA)
        pattern = re.compile(re.escape(surface_nfkc), flags=re.IGNORECASE)
        prepared.append((pattern, surface_nfkc, pronunciation_hira))

    prepared.sort(key=lambda entry: len(entry[1]), reverse=True)
    return prepared


def apply_reading_overrides(text: str, overrides: list[tuple[str, str]]) -> str:
    """登録された表記を、その読みへ置き換える。"""

    # 本文と辞書の両方をNFKC正規化して、全角/半角の違いを吸収する。
    text = unicodedata.normalize("NFKC", text)
    if not text:
        return text

    entries = _prepare(overrides)
    if not entries:
        return text

    bounds = token_boundaries(text)

    parts: list[str] = []
    position = 0
    while position < len(text):
        for pattern, surface, pronunciation in entries:
            matched = pattern.match(text, position)
            if matched is None:
                continue
            end = matched.end()
            if bounds is None:
                if not _is_run_boundary(text, position, end, surface):
                    continue
            elif position not in bounds or end not in bounds:
                continue
            parts.append(pronunciation)
            position = end
            break
        else:
            parts.append(text[position])
            position += 1

    return "".join(parts)
