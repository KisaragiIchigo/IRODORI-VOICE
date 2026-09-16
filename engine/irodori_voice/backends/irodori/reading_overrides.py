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


def apply_reading_overrides(text: str, overrides: list[tuple[str, str]]) -> str:
    """登録された表記を、その読みへ置き換える。

    ``overrides`` は長い表記から順に並んでいる前提で受け取る。「楽天」と
    「楽天ペイ」が両方登録されている場合、短い方を先に当てると残りが
    「ラクテンペイ」ではなく「ラクテン ペイ」のように割れるため。
    """

    for surface, pronunciation in overrides:
        if surface in text:
            text = text.replace(surface, pronunciation)
    return text
