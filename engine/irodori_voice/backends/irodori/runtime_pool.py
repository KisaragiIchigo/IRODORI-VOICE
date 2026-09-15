"""常駐する推論ランタイムの LRU プール。

ベンダリング元の ``get_cached_runtime`` はスロットが 1 つだけで、設定を切り替えるたびに
2.9GB のモデルを捨てて読み直す。話者ごとに LoRA や精度が変わる使い方だと毎回数十秒待たされるため、
ここで複数エントリを保持できるプールに置き換えている。

エントリの追い出しは ``acquire`` の内側でしか起きない。呼び出し側が合成ロックの中から
呼ぶ契約にすることで、使用中のランタイムが解放される状況を作らない。
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from ...vendor.irodori_tts.inference_runtime import InferenceRuntime, RuntimeKey


class RuntimePool:
    def __init__(self, max_entries: int = 1) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be >= 1, got {max_entries}")
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: OrderedDict[RuntimeKey, InferenceRuntime] = OrderedDict()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def acquire(self, key: RuntimeKey) -> tuple[InferenceRuntime, bool]:
        """ランタイムと「今回新規ロードしたか」を返す。"""

        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                return existing, False

            while len(self._entries) >= self._max_entries:
                _, evicted = self._entries.popitem(last=False)
                evicted.unload()

            runtime = InferenceRuntime.from_key(key)
            self._entries[key] = runtime
            return runtime, True

    def loaded_keys(self) -> list[RuntimeKey]:
        with self._lock:
            return list(self._entries.keys())

    def is_loaded(self, key: RuntimeKey) -> bool:
        with self._lock:
            return key in self._entries

    def evict_all(self) -> None:
        with self._lock:
            while self._entries:
                _, runtime = self._entries.popitem(last=False)
                runtime.unload()
