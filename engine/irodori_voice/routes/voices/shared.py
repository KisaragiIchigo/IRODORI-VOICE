"""話者の口すべてが使う土台。

プリセットを応答の形へ直す変換と、アップロードされたファイルの受け止め。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile

from ...backends.base import BackendError
from ...backends.irodori.backend import voice_id_for
from ...paths import voice_assets_dir
from ...schemas import VoiceCapabilitiesOut, VoiceOut, VoiceStyleOut
from ...state import EngineState
from ...voicevox.speaker_image import icon_source

ALLOWED_AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}

MAX_UPLOAD_BYTES = 64 * 1024 * 1024


def engine_state(request: Request) -> EngineState:
    return request.app.state.engine


def voice_out(voice) -> VoiceOut:
    return VoiceOut(
        voice_id=voice.voice_id,
        backend_id=voice.backend_id,
        name=voice.name,
        description=voice.description,
        color_key=voice.color_key,
        styles=[
            VoiceStyleOut(style_id=s.style_id, name=s.name, emoji=getattr(s, "emoji", None))
            for s in voice.styles
        ],
        capabilities=VoiceCapabilitiesOut(
            speed=voice.capabilities.speed,
            volume=voice.capabilities.volume,
            pitch=voice.capabilities.pitch,
            intonation=voice.capabilities.intonation,
            caption=voice.capabilities.caption,
            emoji_style=voice.capabilities.emoji_style,
            reference_audio=voice.capabilities.reference_audio,
            style_strength=voice.capabilities.style_strength,
            seed=voice.capabilities.seed,
            steps=voice.capabilities.steps,
        ),
        sample_rate=voice.sample_rate,
        icon_source=icon_source(voice),
        is_builtin=voice.is_builtin,
        voice_seed=voice.voice_seed,
        has_reference=voice.has_reference,
    )


def voice_out_for_preset(state: EngineState, preset) -> VoiceOut:
    """保存した直後のプリセットを、話者一覧と同じ表現で返す。"""

    voice_id = voice_id_for(preset)
    return voice_out(next(v for v in state.irodori.list_voices() if v.voice_id == voice_id))


def save_upload(upload: UploadFile, *, allowed: set[str], prefix: str) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"対応していない形式です: {suffix or '(拡張子なし)'}",
        )

    target_name = f"{prefix}-{uuid.uuid4().hex[:12]}{suffix}"
    target_path = voice_assets_dir() / target_name

    written = 0
    with target_path.open("wb") as handle:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                handle.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="ファイルが大きすぎます。")
            handle.write(chunk)
    return target_name


def find_voice(request: Request, voice_id: str):
    """話者を引き当てる。ここを通した ID だけを保管のキーに使う。"""

    state = engine_state(request)
    if state.registry is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    try:
        return state.registry.find_voice(voice_id)
    except BackendError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
