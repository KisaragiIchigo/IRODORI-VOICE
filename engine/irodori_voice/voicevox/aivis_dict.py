"""AivisSpeech のユーザー辞書ファイルとの相互変換。

AivisSpeech は登録した語を JSON へ書き出せる。同じ語を両方のソフトで使い回せるよう、
その形のまま読み書きする。互換 API が扱う形とよく似ているが、違いが 2 つある。

  * キーがキャメルケース（``contextId``）で、互換 API はスネークケース（``context_id``）
  * ``stem`` ``yomi`` ``pronunciation`` ``accentType`` ``moraCount`` が配列

配列なのは AivisSpeech が 1 語を複数の形態素へ分けて持てるため。こちらは 1 語 1 形態素
なので、書き出すときは要素 1 つの配列にし、読み込むときは連結して 1 つへ畳む。

読み込みは外から来たファイルを受ける境界なので、値はここで検算してから UserDictWord
へ渡す。特にモーラ数は書かれた値を信じず読みから数え直す。食い違ったまま辞書へ入れると
アクセントの位置だけが静かにずれ、登録した本人には原因が見えない。
"""

from __future__ import annotations

import re
import uuid as uuid_module
from dataclasses import dataclass, replace
from typing import Any

from .user_dict import (
    MAX_PRIORITY,
    MIN_PRIORITY,
    UserDictWord,
    WordType,
    count_moras,
    is_valid_context_id,
    word_type_of,
)

# 読みとして受け付ける文字。カタカナと長音だけを通す。ひらがなや漢字が混ざった読みは
# OpenJTalk がそのまま音へ変換できず、その語だけが読み上げから外れる。
_KATAKANA_ONLY = re.compile("\\A[ァ-ヴー]+\\Z")

# 語の識別子が UUID でなかったときに、同じ鍵から必ず同じ UUID を作るための名前空間。
# 取り込むたびに新しい識別子を振ると、同じファイルを 2 回読んだだけで語が二重になる。
_KEY_NAMESPACE = uuid_module.UUID("2f0c6a5e-9d3b-5f7a-b1c4-8e6d0a2f4b93")

# 取り込みで受け付ける品詞の種別。
_KNOWN_WORD_TYPES: frozenset[str] = frozenset(WordType.__args__)  # type: ignore[attr-defined]


def to_aivis_word(word: UserDictWord) -> dict[str, Any]:
    """1 語を AivisSpeech の形へ直す。"""

    # 原形が埋まっていない語は表記で埋める。AivisSpeech は原形を単語の一覧へ出すため、
    # "*" のまま渡すと向こうでアスタリスクが並ぶ。
    stem = word.stem if word.stem and word.stem != "*" else word.surface
    return {
        "surface": word.surface,
        "priority": word.priority,
        "contextId": word.context_id,
        "partOfSpeech": word.part_of_speech,
        "partOfSpeechDetail1": word.part_of_speech_detail_1,
        "partOfSpeechDetail2": word.part_of_speech_detail_2,
        "partOfSpeechDetail3": word.part_of_speech_detail_3,
        "wordType": word_type_of(word),
        "inflectionalType": word.inflectional_type,
        "inflectionalForm": word.inflectional_form,
        "stem": [stem],
        "yomi": [word.yomi],
        "pronunciation": [word.pronunciation],
        "accentType": [word.accent_type],
        "moraCount": [word.mora_count],
        "accentAssociativeRule": word.accent_associative_rule,
    }


def to_aivis_words(words: dict[str, UserDictWord]) -> dict[str, dict[str, Any]]:
    """辞書まるごとを AivisSpeech の形へ直す。読みの順に並べる。"""

    ordered = sorted(words.items(), key=lambda item: (item[1].yomi, item[1].surface))
    return {word_uuid: to_aivis_word(word) for word_uuid, word in ordered}


@dataclass(frozen=True)
class AivisImportResult:
    """取り込みの結果。受け取れた語と、受け取れなかった語の理由を持つ。"""

    words: dict[str, UserDictWord]
    skipped: list[str]


def from_aivis_words(payload: Any) -> AivisImportResult:
    """AivisSpeech の形の辞書を読み取る。

    受け取れない語はその語だけを外し、理由を添えて返す。1 語の不備でファイル全体を
    突き返すと、何十語もある辞書のどこが悪いのか利用者には辿れない。
    """

    if not isinstance(payload, dict):
        raise ValueError("辞書ファイルの中身が、単語の一覧になっていません。")

    words: dict[str, UserDictWord] = {}
    skipped: list[str] = []
    for key, raw in payload.items():
        if not isinstance(raw, dict):
            skipped.append(f"{key}: 単語の形をしていません。")
            continue
        try:
            words[_normalize_key(str(key))] = _read_word(raw)
        except ValueError as exc:
            surface = raw.get("surface")
            label = surface if isinstance(surface, str) and surface else str(key)
            skipped.append(f"{label}: {exc}")
    return AivisImportResult(words=words, skipped=skipped)


def _normalize_key(key: str) -> str:
    """語の識別子を UUID へ揃える。"""

    try:
        return str(uuid_module.UUID(key))
    except ValueError:
        return str(uuid_module.uuid5(_KEY_NAMESPACE, key))


def _read_word(raw: dict[str, Any]) -> UserDictWord:
    surface = _read_text(raw, "surface")
    if not surface:
        raise ValueError("表記が空です。")

    pronunciation = _join_list(raw, "pronunciation") or _join_list(raw, "yomi")
    if not pronunciation:
        raise ValueError("読みが空です。")
    if not _KATAKANA_ONLY.match(pronunciation):
        raise ValueError(f"読み「{pronunciation}」にカタカナ以外が混ざっています。")

    # 書かれたモーラ数ではなく読みから数え直した値で押さえる。アクセント核が語の
    # 末尾を越えると、OpenJTalk は位置を解釈できない。
    mora_count = count_moras(pronunciation)
    accent_type = max(0, min(_read_first_int(raw, "accentType", default=0), mora_count))
    priority = max(MIN_PRIORITY, min(MAX_PRIORITY, _read_int(raw, "priority", default=5)))

    word = UserDictWord.build(
        surface=surface,
        pronunciation=pronunciation,
        accent_type=accent_type,
        word_type=_read_word_type(raw),
        priority=priority,
    )

    # 原形は元の入力表記が残っている唯一の場所。AivisSpeech では「Ｏ－ＲＡＮ」と
    # 入力した語の表記が「Ｏラン」へ変わるため、ここを捨てると往復で失われる。
    return replace(word, stem=_join_list(raw, "stem") or surface)


def _read_word_type(raw: dict[str, Any]) -> WordType:
    """品詞の種別を決める。

    種別の名前を第一の手がかりにする。文脈 ID は辞書ごとに割り当てが違い、相手の値を
    そのまま持ち込むと辞書のビルドから外れる語が出るため、名前から引き直した値を使う。
    名前が読めないときに限り、書かれている文脈 ID と品詞から言い当てる。
    """

    named = raw.get("wordType")
    if isinstance(named, str) and named in _KNOWN_WORD_TYPES:
        return named  # type: ignore[return-value]

    context_id = _read_int(raw, "contextId", default=-1)
    probe = UserDictWord(
        surface="_",
        priority=MIN_PRIORITY,
        context_id=context_id if is_valid_context_id(context_id) else -1,
        part_of_speech=_read_text(raw, "partOfSpeech"),
        part_of_speech_detail_1=_read_text(raw, "partOfSpeechDetail1"),
        part_of_speech_detail_2=_read_text(raw, "partOfSpeechDetail2"),
        part_of_speech_detail_3=_read_text(raw, "partOfSpeechDetail3"),
        inflectional_type="*",
        inflectional_form="*",
        stem="*",
        yomi="ア",
        pronunciation="ア",
        accent_type=0,
        mora_count=1,
    )
    return word_type_of(probe)


def _read_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    return value.strip() if isinstance(value, str) else ""


def _join_list(raw: dict[str, Any], key: str) -> str:
    """配列で来る欄を 1 つの文字列へ畳む。素の文字列で来ても受ける。"""

    value = raw.get(key)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "".join(part.strip() for part in value if isinstance(part, str))
    return ""


def _read_int(raw: dict[str, Any], key: str, *, default: int) -> int:
    value = raw.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def _read_first_int(raw: dict[str, Any], key: str, *, default: int) -> int:
    value = raw.get(key)
    if isinstance(value, list):
        for part in value:
            if isinstance(part, int) and not isinstance(part, bool):
                return part
        return default
    return _read_int(raw, key, default=default)
