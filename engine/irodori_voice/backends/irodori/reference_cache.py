"""参照音声を DACVAE latent へエンコードした結果のディスクキャッシュ。

同じ話者で 2 行目以降を合成するたびに参照音声を encode し直すのは、体感で一番効く無駄。
encode 結果を ``.pt`` に落としておき、以降は ``SamplingRequest.ref_latents`` 経由で渡す。

latent 経路と wav 経路が同じ音になるよう、``_load_reference_latent`` の wav 側前処理
（単一ファイル時の秒数トリム、ラウドネス正規化、ピーク保護）をそのまま再現している。
"""

from __future__ import annotations

import hashlib
import math
import threading
from pathlib import Path

import torch

from ...paths import latent_cache_dir
from ...vendor.irodori_tts.inference_runtime import InferenceRuntime

# ベンダリング元の内部ヘルパ。wav の読み込み手順がズレると音が変わるため、
# 自前実装で置き換えずに同じ関数を使う。
from ...vendor.irodori_tts.inference_runtime import _load_audio as load_reference_audio

CACHE_FORMAT_VERSION = 1


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReferenceLatentCache:
    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self._root = latent_cache_dir()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _cache_path(
        self,
        *,
        wav_path: Path,
        runtime: InferenceRuntime,
        normalize_db: float | None,
        ensure_max: bool,
        trim_seconds: float | None,
    ) -> Path:
        signature = "|".join(
            [
                f"v{CACHE_FORMAT_VERSION}",
                _file_digest(wav_path),
                str(runtime.key.codec_repo),
                str(runtime.key.codec_precision),
                str(runtime.key.codec_deterministic_encode),
                "none" if normalize_db is None else f"{float(normalize_db):.4f}",
                "1" if ensure_max else "0",
                "none" if trim_seconds is None else f"{float(trim_seconds):.4f}",
            ]
        )
        name = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        return self._root / f"{name}.pt"

    def resolve(
        self,
        wav_paths: list[str],
        *,
        runtime: InferenceRuntime,
        normalize_db: float | None,
        ensure_max: bool,
        max_ref_seconds: float | None,
    ) -> list[str]:
        """wav のリストを、キャッシュ済み latent ファイルのリストへ変換する。

        キャッシュが無効なら空リストを返し、呼び出し側は wav 経路にフォールバックする。
        """

        if not self._enabled or not wav_paths:
            return []

        effective_max = (
            runtime.default_max_ref_seconds if max_ref_seconds is None else float(max_ref_seconds)
        )
        # 元実装は参照が 1 本のときだけ wav 段階で秒数トリムする。
        trim_seconds = effective_max if (len(wav_paths) == 1 and effective_max > 0) else None

        resolved: list[str] = []
        with self._lock:
            for raw_path in wav_paths:
                wav_path = Path(raw_path)
                if not wav_path.is_file():
                    raise FileNotFoundError(f"参照音声が見つかりません: {wav_path}")

                cache_path = self._cache_path(
                    wav_path=wav_path,
                    runtime=runtime,
                    normalize_db=normalize_db,
                    ensure_max=ensure_max,
                    trim_seconds=trim_seconds,
                )
                if not cache_path.is_file():
                    latent = self._encode(
                        wav_path=wav_path,
                        runtime=runtime,
                        normalize_db=normalize_db,
                        ensure_max=ensure_max,
                        trim_seconds=trim_seconds,
                    )
                    tmp_path = cache_path.with_suffix(".pt.tmp")
                    torch.save(latent, tmp_path)
                    tmp_path.replace(cache_path)
                resolved.append(str(cache_path))
        return resolved

    @staticmethod
    def _encode(
        *,
        wav_path: Path,
        runtime: InferenceRuntime,
        normalize_db: float | None,
        ensure_max: bool,
        trim_seconds: float | None,
    ) -> torch.Tensor:
        wav, sample_rate = load_reference_audio(wav_path)
        if trim_seconds is not None:
            max_samples = max(1, int(trim_seconds * float(sample_rate)))
            if wav.shape[1] > max_samples:
                wav = wav[:, :max_samples]

        latent = runtime.codec.encode_waveform(
            wav.unsqueeze(0),
            sample_rate=int(sample_rate),
            normalize_db=normalize_db,
            ensure_max=ensure_max,
        ).cpu()
        if latent.shape[1] == 0:
            raise ValueError(f"参照音声から latent を生成できませんでした: {wav_path}")
        # (1, T, D) のバッチ次元を落として保存する。読み込み側が単体 latent を想定するため。
        return latent[0].contiguous()

    def estimated_steps(self, *, seconds: float, runtime: InferenceRuntime) -> int:
        hop_length = int(runtime.codec.model.hop_length)
        return max(1, math.ceil(seconds * float(runtime.codec.sample_rate) / float(hop_length)))

    def clear(self) -> None:
        with self._lock:
            for path in self._root.glob("*.pt"):
                path.unlink(missing_ok=True)
