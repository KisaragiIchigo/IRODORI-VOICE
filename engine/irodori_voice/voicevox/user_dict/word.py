"""登録語 1 つぶんの表現と、その値が取りうる範囲。

品詞ごとの文脈 ID、優先度とコストの対応、読みのモーラ数え。naist-jdic の
決まりごとに合わせる仕事はすべてここへ閉じ込め、辞書全体の管理からは分ける。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

WordType = Literal[
    "PROPER_NOUN",
    "ORGANIZATION_NAME",
    "PERSON_NAME",
    "COMMON_NOUN",
    "VERB",
    "ADJECTIVE",
    "SUFFIX",
]

MIN_PRIORITY = 0

MAX_PRIORITY = 10

DEFAULT_PRIORITY = 5

# priority 0（最低）から 10（最高）に対応するコスト。値が小さいほど優先して採用される。
_COST_CANDIDATES = [15008, 13728, 12448, 11168, 9888, 8608, 7328, 6048, 4768, 3488, -988]

# 品詞ごとの文脈 ID と品詞細分類。naist-jdic の定義に対応する。
#
# 文脈 ID は naist-jdic の left-id で、辞書が持たない値を渡すと mecab_dict_index が
# その行だけを捨てる。捨てても他の語のビルドは通るため、エラーにはならず「その語
# だけ読みが変わらない」という形で出る。同梱の pyopenjtalk 0.4.1-post9 が抱える
# naist-jdic では 1376 が上限で、VOICEVOX ENGINE が SUFFIX へ使う 1417 は範囲外。
# 接尾は AivisSpeech と同じ 1358 を使う。辞書ファイルを相互に持ち運ぶ相手でもある。
_WORD_TYPE_TABLE: dict[str, tuple[int, str, str, str, str]] = {
    "PROPER_NOUN": (1348, "名詞", "固有名詞", "一般", "*"),
    "ORGANIZATION_NAME": (1352, "名詞", "固有名詞", "組織", "*"),
    "PERSON_NAME": (1349, "名詞", "固有名詞", "人名", "一般"),
    "COMMON_NOUN": (1345, "名詞", "一般", "*", "*"),
    "VERB": (642, "動詞", "自立", "*", "*"),
    "ADJECTIVE": (20, "形容詞", "自立", "*", "*"),
    "SUFFIX": (1358, "名詞", "接尾", "一般", "*"),
}

# naist-jdic が持つ left-id の上限。これを超える文脈 ID の語は辞書へ入らない。
MAX_CONTEXT_ID = 1376

# モーラの区切り。長い並びから順に当てる。小書きのカナを一律で直前へ吸収すると、
# 「ビィ」のように 2 モーラで数える並びまで 1 モーラになり、アクセント位置が
# 1 つずれる。どの並びを 1 モーラとするかは VOICEVOX ENGINE に合わせてある。
_MORA_PATTERN = re.compile(
    "|".join(
        [
            "[イ][ェ]",
            "[ヴ][ャュョ]",
            "[トド][ゥ]",
            "[テデ][ィャュョ]",
            "[デ][ェ]",
            "[クグ][ヮ]",
            "[キシチニヒミリギジビピ][ェャュョ]",
            "[ツフヴ][ァィェォ]",
            "[ァ-ヴー]",
        ]
    )
)


def count_moras(pronunciation: str) -> int:
    """カタカナの発音からモーラ数を数える。"""

    return max(1, len(_MORA_PATTERN.findall(pronunciation)))


@dataclass
class UserDictWord:
    surface: str
    priority: int
    context_id: int
    part_of_speech: str
    part_of_speech_detail_1: str
    part_of_speech_detail_2: str
    part_of_speech_detail_3: str
    inflectional_type: str
    inflectional_form: str
    stem: str
    yomi: str
    pronunciation: str
    accent_type: int
    mora_count: int
    accent_associative_rule: str = "*"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> UserDictWord:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known})

    @classmethod
    def build(
        cls,
        *,
        surface: str,
        pronunciation: str,
        accent_type: int,
        word_type: WordType = "PROPER_NOUN",
        priority: int = DEFAULT_PRIORITY,
    ) -> UserDictWord:
        context_id, pos, detail_1, detail_2, detail_3 = _WORD_TYPE_TABLE.get(
            word_type, _WORD_TYPE_TABLE["PROPER_NOUN"]
        )
        return cls(
            surface=surface,
            priority=max(MIN_PRIORITY, min(MAX_PRIORITY, int(priority))),
            context_id=context_id,
            part_of_speech=pos,
            part_of_speech_detail_1=detail_1,
            part_of_speech_detail_2=detail_2,
            part_of_speech_detail_3=detail_3,
            inflectional_type="*",
            inflectional_form="*",
            stem="*",
            yomi=pronunciation,
            pronunciation=pronunciation,
            accent_type=int(accent_type),
            mora_count=count_moras(pronunciation),
        )

    def to_csv_row(self) -> str:
        cost = _COST_CANDIDATES[max(MIN_PRIORITY, min(MAX_PRIORITY, self.priority))]
        return ",".join(
            [
                self.surface,
                str(self.context_id),
                str(self.context_id),
                str(cost),
                self.part_of_speech,
                self.part_of_speech_detail_1,
                self.part_of_speech_detail_2,
                self.part_of_speech_detail_3,
                self.inflectional_type,
                self.inflectional_form,
                self.stem,
                self.yomi,
                self.pronunciation,
                f"{self.accent_type}/{self.mora_count}",
                self.accent_associative_rule,
            ]
        )


def word_type_of(word: UserDictWord) -> WordType:
    """登録済みの語がどの品詞として作られたかを言い当てる。

    語そのものには品詞の種別を持たせていない。文脈 ID と品詞細分類の組が
    種別ごとに固有なので、そこから引き直す。どれにも当てはまらない語
    （他のソフトが書いた辞書を取り込んだ場合など）は固有名詞として扱う。
    """

    signature = (
        word.part_of_speech,
        word.part_of_speech_detail_1,
        word.part_of_speech_detail_2,
        word.part_of_speech_detail_3,
    )
    for word_type, (context_id, *details) in _WORD_TYPE_TABLE.items():
        if word.context_id == context_id and tuple(details) == signature:
            return word_type  # type: ignore[return-value]
    for word_type, (_, *details) in _WORD_TYPE_TABLE.items():
        if tuple(details) == signature:
            return word_type  # type: ignore[return-value]
    return "PROPER_NOUN"


def is_valid_context_id(context_id: int) -> bool:
    """その文脈 ID で辞書をビルドできるかを返す。"""

    return 0 <= context_id <= MAX_CONTEXT_ID
