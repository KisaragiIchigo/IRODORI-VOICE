"""話者へ付けるアイコンの取得・差し替え・取り消し。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from ...schemas import VoiceOut
from ...voices.icon_store import (
    ALLOWED_ICON_SUFFIXES,
    MAX_ICON_BYTES,
    IconDecodeError,
    icon_store,
)
from ...voicevox.speaker_image import icon_png
from .shared import find_voice, voice_out

router = APIRouter(tags=["voices"])


@router.get("/voices/{voice_id:path}/icon")
def voice_icon(request: Request, voice_id: str) -> Response:
    """一覧に出るアイコン。付けていない話者も識別色の図形が返る。

    差し替えた直後に古い絵が残らないよう、保存させない。
    """

    voice = find_voice(request, voice_id)
    return Response(
        content=icon_png(voice),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/voices/{voice_id:path}/icon", response_model=VoiceOut)
async def set_voice_icon(
    request: Request,
    voice_id: str,
    icon: UploadFile = File(...),
) -> VoiceOut:
    """話者へアイコンを付ける。同梱話者と取り込んだ話者にも付けられる。

    アイコンは話者の定義とは別に保管しているため、モデルや参照音声には触れない。
    """

    voice = find_voice(request, voice_id)

    suffix = Path(icon.filename or "").suffix.lower()
    if suffix not in ALLOWED_ICON_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"画像ファイルを指定してください（対応: {' / '.join(sorted(ALLOWED_ICON_SUFFIXES))}）。",
        )

    data = await icon.read(MAX_ICON_BYTES + 1)
    if len(data) > MAX_ICON_BYTES:
        raise HTTPException(status_code=400, detail="画像が大きすぎます。16MB までにしてください。")

    try:
        icon_store.save(voice.voice_id, data)
    except IconDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return voice_out(voice)


@router.delete("/voices/{voice_id:path}/icon", response_model=VoiceOut)
def clear_voice_icon(request: Request, voice_id: str) -> VoiceOut:
    """付けたアイコンを外す。話者が元から持つ画像か識別色の図形へ戻る。"""

    voice = find_voice(request, voice_id)
    icon_store.clear(voice.voice_id)
    return voice_out(voice)
