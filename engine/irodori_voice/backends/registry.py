"""バックエンドの束ね役と、合成結果のキャッシュ・先読み。

VOICEVOX 風の操作では「同じ行を何度も再生する」「次の行へ移る前に裏で作っておく」が
体感速度を大きく左右する。モデル自体を速くするのとは別の軸で効くので、ここで面倒を見る。
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from .. import audio as audio_utils
from .base import (
    BackendAvailability,
    BackendError,
    SynthesisBackend,
    SynthesisOutput,
    SynthesisParams,
    VoiceInfo,
)


class BackendRegistry:
    def __init__(self, backends: list[SynthesisBackend]) -> None:
        self._backends = {backend.backend_id: backend for backend in backends}

    def get(self, backend_id: str) -> SynthesisBackend:
        backend = self._backends.get(backend_id)
        if backend is None:
            raise BackendError(f"バックエンド {backend_id} は登録されていません。")
        return backend

    def backend_for_voice(self, voice_id: str) -> SynthesisBackend:
        backend_id, _, _ = voice_id.partition(":")
        return self.get(backend_id)

    def list_voices(self) -> list[VoiceInfo]:
        voices: list[VoiceInfo] = []
        for backend in self._backends.values():
            if not backend.availability().available:
                continue
            voices.extend(backend.list_voices())
        return voices

    def find_voice(self, voice_id: str) -> VoiceInfo:
        for voice in self.list_voices():
            if voice.voice_id == voice_id:
                return voice
        raise BackendError(f"話者 {voice_id} が見つかりません。")

    def availabilities(self) -> list[BackendAvailability]:
        return [backend.availability() for backend in self._backends.values()]

    def shutdown(self) -> None:
        for backend in self._backends.values():
            backend.shutdown()


class SynthesisService:
    """合成の入口。キャッシュ判定と先読みをここで完結させる。

    シードが指定されていない要求は毎回違う声になるのが仕様なので、キャッシュしない。
    エディタ側は行ごとにシードを保持して送るため、通常の操作では必ずキャッシュに乗る。
    """

    def __init__(
        self,
        registry: BackendRegistry,
        *,
        cache_entries: int = 256,
    ) -> None:
        self._registry = registry
        self._cache_entries = max(0, cache_entries)
        self._cache: OrderedDict[tuple, SynthesisOutput] = OrderedDict()
        self._cache_lock = threading.Lock()

        self._prefetch_lock = threading.Lock()
        self._prefetch_pending: SynthesisParams | None = None
        self._prefetch_event = threading.Event()
        self._prefetch_stop = threading.Event()
        self._prefetch_thread: threading.Thread | None = None

    # ------------------------------------------------------------ キャッシュ

    @staticmethod
    def _is_cacheable(params: SynthesisParams) -> bool:
        return params.seed is not None

    def _cache_get(self, key: tuple) -> SynthesisOutput | None:
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
            return hit

    def _cache_put(self, key: tuple, output: SynthesisOutput) -> None:
        if self._cache_entries == 0:
            return
        with self._cache_lock:
            self._cache[key] = output
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_entries:
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    # -------------------------------------------------------------- 合成本体

    def synthesize(self, params: SynthesisParams) -> tuple[SynthesisOutput, bool]:
        """(結果, キャッシュヒットか) を返す。"""

        if params.text.strip() == "":
            raise BackendError("テキストが空です。")

        cacheable = self._is_cacheable(params)
        key = params.cache_fingerprint()
        if cacheable:
            hit = self._cache_get(key)
            if hit is not None:
                return hit, True

        backend = self._registry.backend_for_voice(params.voice_id)
        raw = backend.synthesize(params)

        samples = audio_utils.apply_gain(raw.samples, params.volume)
        samples = audio_utils.pad_silence(
            samples,
            sample_rate=raw.sample_rate,
            pre_seconds=params.pre_silence,
            post_seconds=params.post_silence,
        )
        output = SynthesisOutput(
            samples=samples,
            sample_rate=raw.sample_rate,
            used_seed=raw.used_seed,
            stage_timings=raw.stage_timings,
            notes=raw.notes,
        )

        if cacheable:
            self._cache_put(key, output)
        return output, False

    def is_cached(self, params: SynthesisParams) -> bool:
        if not self._is_cacheable(params):
            return False
        return self._cache_get(params.cache_fingerprint()) is not None

    # ---------------------------------------------------------------- 先読み

    def start_prefetch_worker(self) -> None:
        if self._prefetch_thread is not None:
            return
        self._prefetch_stop.clear()
        thread = threading.Thread(
            target=self._prefetch_loop,
            name="irodori-voice-prefetch",
            daemon=True,
        )
        self._prefetch_thread = thread
        thread.start()

    def request_prefetch(self, params: SynthesisParams) -> bool:
        """次に再生されそうな 1 行を裏で作っておく。

        待ち行列は常に 1 件だけ保持する。溜め込むと、利用者が今すぐ聞きたい行が
        先読みの後ろに並んでしまい、かえって待たされるため。
        """

        if not self._is_cacheable(params) or self.is_cached(params):
            return False
        with self._prefetch_lock:
            self._prefetch_pending = params
        self._prefetch_event.set()
        return True

    def _prefetch_loop(self) -> None:
        while not self._prefetch_stop.is_set():
            self._prefetch_event.wait(timeout=0.5)
            if self._prefetch_stop.is_set():
                return
            self._prefetch_event.clear()

            with self._prefetch_lock:
                params = self._prefetch_pending
                self._prefetch_pending = None
            if params is None:
                continue
            try:
                self.synthesize(params)
            except BackendError:
                # 先読みの失敗は利用者に見せない。実際に再生された時点で同じ例外が報告される。
                continue

    def shutdown(self) -> None:
        self._prefetch_stop.set()
        self._prefetch_event.set()
        thread = self._prefetch_thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._prefetch_thread = None
        self._registry.shutdown()
