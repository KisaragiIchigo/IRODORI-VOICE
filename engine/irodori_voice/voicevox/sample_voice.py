"""話者のサンプルボイス。

VOICEVOX エディタのキャラクター一覧は ``voice_samples`` の先頭を
``audio.src`` へ直接代入して再生する。空配列を返すと undefined が代入され、
NotSupportedError で再生処理ごと落ちる（エディタ側に存在チェックが無い）。

事前収録の音声は持たないので、話者ごとに実際に合成して作る。ただし
``/speaker_info`` は一覧を開いた瞬間に全話者ぶん呼ばれるため、その場で
合成すると数十秒待たされる。そこで次の形にしている。

  1. ディスクに作り置きがあればそれを返す
  2. 無ければ無音を返し、裏で生成を始める
  3. 次に一覧を開いたときには本物が鳴る

生成はエンジンが暇なときに進むよう、1 件ずつ直列で行う。
"""

from __future__ import annotations

import base64
import io
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf

from ..paths import cache_root

SAMPLE_RATE = 24000
SILENT_SECONDS = 0.2

# 試聴で読ませる文。スタイルごとに 1 本だけ作る。
# 全話者・全スタイルで 3 本ずつ作ると 50 本近くになり、初回の生成が長すぎる。
SAMPLE_TEXT = "こんにちは。いろどりボイスです。"


def _sample_dir() -> Path:
    path = cache_root() / "voice-samples"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sample_path(voice_id: str, style_id: str | None, index: int) -> Path:
    key = f"{voice_id}_{style_id or 'default'}_{index}".replace(":", "-").replace("/", "-")
    return _sample_dir() / f"{key}.wav"


def _encode(samples: np.ndarray, rate: int) -> str:
    buffer = io.BytesIO()
    sf.write(buffer, samples.astype(np.float32, copy=False), rate, format="WAV", subtype="PCM_16")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def silent_sample_base64() -> str:
    """まだ生成できていないときに返す、再生可能な無音。"""

    return _encode(np.zeros(int(SAMPLE_RATE * SILENT_SECONDS), dtype=np.float32), SAMPLE_RATE)


class SampleVoiceStore:
    """サンプル音声の作り置きと遅延生成。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: set[tuple[str, str | None]] = set()
        self._worker: threading.Thread | None = None
        self._queue: list[tuple[str, str | None]] = []
        self._generate: Callable[[str, str | None, str], bytes] | None = None

    def bind(self, generate: Callable[[str, str | None, str], bytes]) -> None:
        """合成関数を渡す。エンジンの起動が済んでから呼ぶ。"""

        self._generate = generate

    def samples_for(self, voice_id: str, style_id: str | None, *, count: int = 3) -> list[str]:
        """base64 のサンプルを返す。無ければ無音を返し、生成を予約する。"""

        path = _sample_path(voice_id, style_id, 0)
        if path.is_file():
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        else:
            encoded = silent_sample_base64()
            self._enqueue(voice_id, style_id)

        # エディタは voiceSamplePaths の要素数だけ試聴ボタンを出し、添字で引く。
        # 本家が 3 本持つ形に合わせ、同じ音声を 3 枠に並べる。
        return [encoded] * count

    def _enqueue(self, voice_id: str, style_id: str | None) -> None:
        if self._generate is None:
            return
        key = (voice_id, style_id)
        with self._lock:
            if key in self._pending:
                return
            self._pending.add(key)
            self._queue.append(key)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._run,
                    name="irodori-voice-samples",
                    daemon=True,
                )
                self._worker.start()

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._worker = None
                    return
                voice_id, style_id = self._queue.pop(0)

            try:
                self._generate_all(voice_id, style_id)
            except Exception:
                # 生成に失敗しても一覧の表示は続けられる。次回また試す。
                pass
            finally:
                with self._lock:
                    self._pending.discard((voice_id, style_id))

    def _generate_all(self, voice_id: str, style_id: str | None) -> None:
        if self._generate is None:
            return
        path = _sample_path(voice_id, style_id, 0)
        if path.is_file():
            return
        wav = self._generate(voice_id, style_id, SAMPLE_TEXT)
        tmp = path.with_suffix(".wav.tmp")
        tmp.write_bytes(wav)
        tmp.replace(path)

    def clear(self) -> None:
        for path in _sample_dir().glob("*.wav"):
            path.unlink(missing_ok=True)


# エンジン全体で 1 つ。/speaker_info から参照する。
sample_store = SampleVoiceStore()
