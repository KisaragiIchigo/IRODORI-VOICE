"""ユーザー辞書の登録語を、モデルへ渡すテキストの上で置き換える。

Irodori-TTS は ``SamplingRequest.text`` の表記から直接音を作るモデルで、読み仮名を
受け取る口を持たない。そのため OpenJTalk のユーザー辞書は Irodori 話者の発音に
届かず（AIVM 話者には ``.dic`` 経由で効く）、読みを直す手段が表記の書き換えしか
ない。

実測でも、表記の違いがそのまま発音の成否になる。同じ話者・同じ設定で「楽天モバイル」
と書くと別の語に化けるが、「ラクテン」と書けば正しく読まれる。この差を利用者が
本文へ手で書き込まずに済むよう、辞書の登録語をここで当てる。
"""

from __future__ import annotations


_KANA_TO_HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポァィゥェォャュョッヴ",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっゔ"
)

import re
import unicodedata

def apply_reading_overrides(text: str, overrides: list[tuple[str, str]]) -> str:
    """登録された表記を、その読みへ置き換える。

    ``overrides`` は長い表記から順に並んでいる前提で受け取る。「楽天」と
    「楽天ペイ」が両方登録されている場合、短い方を先に当てると残りが
    「ラクテンペイ」ではなく「ラクテン ペイ」のように割れるため。
    """

    # 本文と辞書の両方をNFKC正規化して、全角/半角の違いを吸収する。
    text = unicodedata.normalize("NFKC", text)

    for surface, pronunciation in overrides:
        surface_nfkc = unicodedata.normalize("NFKC", surface)
        # VOICEVOXエディタは辞書の「読み」をカタカナで強制するが、
        # Irodori-TTSにカタカナをそのまま渡すと外来語のような不自然なイントネーションになる。
        # そこで、置換前にカタカナをひらがなへ変換する。
        pronunciation_hira = pronunciation.translate(_KANA_TO_HIRA)
        
        # 大文字小文字を無視して置換
        pattern = re.compile(re.escape(surface_nfkc), flags=re.IGNORECASE)
        text = pattern.sub(pronunciation_hira, text)
        
    return text
