"""波形の後処理と wav エンコード。

バックエンドが返すのは「合成された声そのもの」だけ。音量・前後の間・行の連結は
どのバックエンドでも同じ扱いでよいので、ここに集約している。
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

MAX_SILENCE_SECONDS = 10.0


def apply_gain(samples: np.ndarray, volume: float) -> np.ndarray:
    if volume == 1.0:
        return samples
    scaled = samples * float(volume)
    # 音量を上げた結果のクリップは耳に付くので、最大値が 1 を超える場合だけ正規化する。
    peak = float(np.max(np.abs(scaled))) if scaled.size else 0.0
    if peak > 1.0:
        scaled = scaled / peak
    return scaled.astype(np.float32, copy=False)


def pad_silence(
    samples: np.ndarray,
    *,
    sample_rate: int,
    pre_seconds: float,
    post_seconds: float,
) -> np.ndarray:
    pre = int(max(0.0, min(MAX_SILENCE_SECONDS, pre_seconds)) * sample_rate)
    post = int(max(0.0, min(MAX_SILENCE_SECONDS, post_seconds)) * sample_rate)
    if pre == 0 and post == 0:
        return samples
    return np.concatenate(
        [
            np.zeros((pre, *samples.shape[1:]), dtype=np.float32),
            samples.astype(np.float32, copy=False),
            np.zeros((post, *samples.shape[1:]), dtype=np.float32),
        ]
    )


def concat_segments(segments: list[np.ndarray]) -> np.ndarray:
    if not segments:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate([s.astype(np.float32, copy=False) for s in segments])


def normalize_pcm16_peak(samples: np.ndarray) -> np.ndarray:
    """16bit の振幅上限を超える場合だけ、全チャンネル共通で減衰する。"""
    limit = 32767 / 32768
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    return samples * (limit / peak) if peak > limit else samples


def encode_wav(samples: np.ndarray, *, sample_rate: int, subtype: str = "PCM_16") -> bytes:
    buffer = io.BytesIO()
    if subtype == "PCM_16":
        samples = normalize_pcm16_peak(samples)
    sf.write(buffer, samples.astype(np.float32, copy=False), int(sample_rate), format="WAV", subtype=subtype)
    return buffer.getvalue()


def as_stereo(samples: np.ndarray) -> np.ndarray:
    """左右がある波形は保ち、モノラルだけを左右へ複製する。"""
    if samples.ndim == 1:
        return np.repeat(samples[:, None], 2, axis=1)
    return np.repeat(samples, 2, axis=1) if samples.shape[1] == 1 else samples


def encode_wav_stereo(samples: np.ndarray, *, sample_rate: int, subtype: str = "PCM_16") -> bytes:
    """モノラル波形を 2 チャンネルに複製して書き出す。

    VOICEVOX の ``outputStereo`` に相当する。合成そのものはモノラルなので、
    左右に同じ信号を置くだけで定位は作らない。
    """

    stereo = as_stereo(samples.astype(np.float32, copy=False))
    return encode_wav(stereo, sample_rate=sample_rate, subtype=subtype)


def resample(samples: np.ndarray, *, source_rate: int, target_rate: int) -> np.ndarray:
    """サンプリングレートを変換する。

    ダウンサンプリングでは折り返し歪みを避けるためのローパスが要る。torchaudio の
    リサンプラはそれを含むので、利用できる場合はそちらを使い、無い場合だけ
    線形補間へ落とす。
    """

    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)

    try:
        import torch
        import torchaudio

        channels = samples[None, :] if samples.ndim == 1 else samples.T
        tensor = torch.from_numpy(np.ascontiguousarray(channels, dtype=np.float32))
        converted = torchaudio.functional.resample(tensor, int(source_rate), int(target_rate))
        result = converted.numpy()
        return (result[0] if samples.ndim == 1 else result.T).astype(np.float32, copy=False)
    except Exception:
        return resample_linear(samples, source_rate=source_rate, target_rate=target_rate)


def resample_linear(samples: np.ndarray, *, source_rate: int, target_rate: int) -> np.ndarray:
    """線形補間による変換。

    torchaudio が使えない場合の代替。アップサンプリングでは実用上問題ないが、
    ダウンサンプリングでは折り返しが残る。
    """

    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    duration = len(samples) / float(source_rate)
    target_length = max(1, int(round(duration * target_rate)))
    source_positions = np.linspace(0.0, duration, num=len(samples), endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    if samples.ndim == 1:
        return np.interp(target_positions, source_positions, samples).astype(np.float32)
    return np.stack([
        np.interp(target_positions, source_positions, channel) for channel in samples.T
    ], axis=1).astype(np.float32)
