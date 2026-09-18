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
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np

from ..paths import cache_root
from ..audio import encode_wav_stereo

SAMPLE_RATE = 24000
SILENT_SECONDS = 0.2

# 試聴で読ませる文。スタイルごとに 1 本だけ作る。
# 全話者・全スタイルで 3 本ずつ作ると 50 本近くになり、初回の生成が長すぎる。
SAMPLE_TEXT = "こんにちは。いろどりボイスです。"

# 読み取るサンプルの上限。いまは 1 話者につき 1 本しか作らないが、後から
# 増やしたときに samples_for が拾えるよう、連番を追える形にしておく。
_MAX_SAMPLES = 3


def _sample_dir() -> Path:
    path = cache_root() / "voice-samples"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sample_path(voice_id: str, style_id: str | None, index: int) -> Path:
    # モノラル出力の旧キャッシュは再利用しない。
    key = f"v3_{voice_id}_{style_id or 'default'}_{index}".replace(":", "-").replace("/", "-")
    return _sample_dir() / f"{key}.wav"


def _encode(samples: np.ndarray, rate: int) -> str:
    return base64.b64encode(encode_wav_stereo(samples, sample_rate=rate)).decode("ascii")


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

    def samples_for(self, voice_id: str, style_id: str | None) -> list[str]:
        """base64 のサンプルを返す。無ければ無音を返し、生成を予約する。

        エディタは要素数だけ試聴ボタンを出すため、持っている本数をそのまま返す。
        本家は 1 話者につき 3 本のサンプルを用意しているが、こちらは 1 本しか作らない。
        3 枠へ同じ音声を並べると、押しても同じ音が鳴るボタンが 3 つ並ぶことになる。
        """

        encoded: list[str] = []
        for index in range(_MAX_SAMPLES):
            path = _sample_path(voice_id, style_id, index)
            if not path.is_file():
                break
            encoded.append(base64.b64encode(path.read_bytes()).decode("ascii"))

        if encoded:
            return encoded

        # まだ作られていない。空配列を返すとエディタが undefined を audio.src へ
        # 代入して落ちるため、無音を 1 本返しておく。生成は裏で走らせる。
        self._enqueue(voice_id, style_id)
        return [silent_sample_base64()]

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
