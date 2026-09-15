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
            np.zeros(pre, dtype=np.float32),
            samples.astype(np.float32, copy=False),
            np.zeros(post, dtype=np.float32),
        ]
    )


def concat_segments(segments: list[np.ndarray]) -> np.ndarray:
    if not segments:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate([s.astype(np.float32, copy=False) for s in segments])


def encode_wav(samples: np.ndarray, *, sample_rate: int, subtype: str = "PCM_16") -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples.astype(np.float32, copy=False), int(sample_rate), format="WAV", subtype=subtype)
    return buffer.getvalue()


def encode_wav_stereo(samples: np.ndarray, *, sample_rate: int, subtype: str = "PCM_16") -> bytes:
    """モノラル波形を 2 チャンネルに複製して書き出す。

    VOICEVOX の ``outputStereo`` に相当する。合成そのものはモノラルなので、
    左右に同じ信号を置くだけで定位は作らない。
    """

    mono = samples.astype(np.float32, copy=False)
    stereo = np.stack([mono, mono], axis=1)
    buffer = io.BytesIO()
    sf.write(buffer, stereo, int(sample_rate), format="WAV", subtype=subtype)
    return buffer.getvalue()


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

        tensor = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32)).unsqueeze(0)
        converted = torchaudio.functional.resample(tensor, int(source_rate), int(target_rate))
        return converted.squeeze(0).numpy().astype(np.float32, copy=False)
    except Exception:
        return resample_linear(samples, source_rate=source_rate, target_rate=target_rate)


def resample_linear(samples: np.ndarray, *, source_rate: int, target_rate: int) -> np.ndarray:
    """線形補間による変換。

    torchaudio が使えない場合の代替。アップサンプリングでは実用上問題ないが、
    ダウンサンプリングでは折り返しが残る。
    """

    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    duration = samples.size / float(source_rate)
    target_length = max(1, int(round(duration * target_rate)))
    source_positions = np.linspace(0.0, duration, num=samples.size, endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)
