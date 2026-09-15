"""OpenJTalk のフルコンテキストラベルを解析する。

ラベルは音素 1 つにつき 1 行で、前後の文脈がフィールドとして埋め込まれている。

    xx^xx-sil+k=o/A:xx+xx+xx/B:...-...-.../C:.../D:.../E:.../F:5_2#0_xx@1_3|1_9/...

アクセント句の切れ目を知るのに必要なのは次の 3 つ。

    音素      ``-`` と ``+`` に挟まれた部分
    A:a2      アクセント句内で何モーラ目か。1 に戻るところが新しいアクセント句
    F:f1_f2   そのアクセント句のモーラ数とアクセント型（0 は平板）

句読点だけで区切ると「ジカンヲカケテナイヨーヲリカイスルバメント」のように
1 つのアクセント句が長くなりすぎる。ラベルを読めば本家と同じ単位で割れる。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 母音と特殊音素。これ以外は子音として直後の母音とひとまとまりにする。
VOWELS = frozenset("aiueoAIUEO") | {"N", "cl"}
PAUSES = frozenset({"pau", "sil"})

_PHONEME = re.compile(r"\-([^\+]+)\+")
_A_FIELD = re.compile(r"/A:(-?\d+|xx)\+(\d+|xx)\+(\d+|xx)")
_F_FIELD = re.compile(r"/F:(\d+|xx)_(\d+|xx)")


@dataclass(frozen=True)
class Label:
    """ラベル 1 行から取り出した、アクセント句の構成に必要な情報。"""

    phoneme: str
    # アクセント句内でのモーラ位置。1 が先頭。
    mora_position: int
    # アクセント句のモーラ数とアクセント型。
    mora_count: int
    accent_type: int

    @property
    def is_pause(self) -> bool:
        return self.phoneme in PAUSES

    @property
    def is_vowel(self) -> bool:
        return self.phoneme in VOWELS


def _to_int(value: str) -> int:
    return 0 if value == "xx" else int(value)


def parse_label(label: str) -> Label | None:
    """ラベル 1 行を解析する。解釈できない行は None を返す。"""

    phoneme_match = _PHONEME.search(label)
    if phoneme_match is None:
        return None

    a_match = _A_FIELD.search(label)
    f_match = _F_FIELD.search(label)

    return Label(
        phoneme=phoneme_match.group(1),
        mora_position=_to_int(a_match.group(2)) if a_match else 0,
        mora_count=_to_int(f_match.group(1)) if f_match else 0,
        accent_type=_to_int(f_match.group(2)) if f_match else 0,
    )


def parse_labels(labels: list[str]) -> list[Label]:
    parsed = [parse_label(label) for label in labels]
    return [label for label in parsed if label is not None]


@dataclass
class LabelPhrase:
    """アクセント句 1 つぶんのラベル列。"""

    labels: list[Label]
    accent_type: int
    # この句の直後に置かれるポーズ。文中の読点などで入る。
    has_pause: bool = False


def group_into_phrases(labels: list[Label]) -> list[LabelPhrase]:
    """ラベル列をアクセント句へ切り分ける。

    ``mora_position`` が 1 に戻るところが新しいアクセント句の先頭。
    ポーズ（pau / sil）は句には含めず、直前の句へ「後ろに間がある」印を付ける。
    """

    phrases: list[LabelPhrase] = []
    current: list[Label] = []
    current_accent = 0
    # 子音は単独ではモーラにならない。直後の母音が来るまで持ち越す。
    # ここで溜めずに current へ入れてしまうと、句の先頭の子音が
    # 前の句に取り残されて「ジカン」が「イカン」になる。
    pending: list[Label] = []

    for label in labels:
        if label.is_pause:
            current.extend(pending)
            pending = []
            if current:
                phrases.append(LabelPhrase(labels=current, accent_type=current_accent))
                current = []
            if phrases:
                # 文頭・文末の無音では印を付けない。句と句の間だけ。
                phrases[-1].has_pause = True
            continue

        if not label.is_vowel:
            pending.append(label)
            continue

        # 母音（= モーラの切れ目）で位置が 1 に戻ったら、そこから次の句。
        # 持ち越した子音は、この母音と同じ句へ入れる。
        if label.mora_position == 1 and current:
            phrases.append(LabelPhrase(labels=current, accent_type=current_accent))
            current = []

        current.extend(pending)
        pending = []
        current.append(label)
        current_accent = label.accent_type

    current.extend(pending)
    if current:
        phrases.append(LabelPhrase(labels=current, accent_type=current_accent))

    # 末尾のポーズ印は不要。連結時に余分な間が入る。
    if phrases:
        phrases[-1].has_pause = False
    return phrases
