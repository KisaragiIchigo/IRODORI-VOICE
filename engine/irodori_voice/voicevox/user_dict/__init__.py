"""ユーザー辞書。

VOICEVOX エディタの辞書画面から追加された語を、実際に OpenJTalk の解析へ反映させる。
保存するだけで読みが変わらない実装にすると、利用者は「登録したのに直らない」という
一番わかりにくい形で裏切られるため、pyopenjtalk のユーザー辞書機構まで通す。

辞書は naist-jdic 互換の CSV へ書き出してから ``.dic`` にビルドする。
この形式と優先度の対応は VOICEVOX ENGINE に合わせている。
"""

from __future__ import annotations

from .dictionary import (
    UserDictionary,
    shared_user_dict,
)
from .word import (
    DEFAULT_PRIORITY,
    MAX_CONTEXT_ID,
    MAX_PRIORITY,
    MIN_PRIORITY,
    UserDictWord,
    WordType,
    count_moras,
    is_valid_context_id,
    word_type_of,
)

__all__ = [
    "DEFAULT_PRIORITY",
    "MAX_CONTEXT_ID",
    "MAX_PRIORITY",
    "MIN_PRIORITY",
    "UserDictWord",
    "UserDictionary",
    "WordType",
    "count_moras",
    "is_valid_context_id",
    "shared_user_dict",
    "word_type_of",
]
