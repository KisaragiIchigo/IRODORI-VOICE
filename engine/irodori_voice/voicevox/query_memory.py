"""AudioQuery と元テキストの対応を覚えておく小さなキャッシュ。

VOICEVOX の ``/synthesis`` は AudioQuery しか受け取らず、元の表記は渡ってこない。
モーラ列から復元できるのはカタカナの読みだけなので、そのまま合成すると
漢字表記から得られるはずの読み分けや抑揚の手がかりが失われる。

``/audio_query`` を通った要求については元テキストを覚えておき、``/synthesis``
で引き当てる。外部ツールは必ず ``/audio_query`` を先に呼ぶため、通常の利用では命中する。
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from .schemas import AccentPhrase

MAX_ENTRIES = 512


def phrase_key(phrases: list[AccentPhrase]) -> str:
    """読みが同じなら同じキーになるようにする。

    アクセント位置や長さを編集されても読みが変わらない限り命中させたいので、
    モーラの表記だけを連結する。
    """

    return "|".join("".join(mora.text for mora in phrase.moras) for phrase in phrases)


class QueryTextMemory:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, str] = OrderedDict()

    def remember(self, phrases: list[AccentPhrase], text: str) -> None:
        key = phrase_key(phrases)
        if key == "":
            return
        with self._lock:
            self._entries[key] = text
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def recall(self, phrases: list[AccentPhrase]) -> str | None:
        key = phrase_key(phrases)
        if key == "":
            return None
        with self._lock:
            text = self._entries.get(key)
            if text is not None:
                self._entries.move_to_end(key)
            return text

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
