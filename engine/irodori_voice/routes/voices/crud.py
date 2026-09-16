"""話者そのものの出し入れ。一覧、作成、書き換え、複製、削除。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...backends.base import BackendError
from ...backends.irodori.backend import preset_id_from
from ...paths import voice_assets_dir
from ...schemas import VoiceCreateRequest, VoiceOut, VoiceUpdateRequest
from ...voices.icon_store import icon_store
from ...voices.store import VoiceStyleDef
from .shared import engine_state, voice_out, voice_out_for_preset

router = APIRouter(tags=["voices"])


@router.get("/voices", response_model=list[VoiceOut])
def list_voices(request: Request) -> list[VoiceOut]:
    state = engine_state(request)
    if state.registry is None:
        return []
    # モデル一覧と同じく、モデルライブラリを読み直してから返す。エンジンを通さずに
    # ライブラリのフォルダへモデルを置いた場合でも、一覧を開けばここで追いつく。
    if state.aivm is not None:
        state.aivm.refresh()
    return [voice_out(voice) for voice in state.registry.list_voices()]


@router.post("/voices", response_model=VoiceOut, status_code=201)
def create_voice(request: Request, payload: VoiceCreateRequest) -> VoiceOut:
    """参照音声を持たない話者（キャプション条件のみ）を作る。"""

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    if payload.mode != "caption":
        raise HTTPException(
            status_code=400,
            detail="参照音声や話者埋め込みを使う話者は /voices/upload から作成してください。",
        )

    preset = state.store.create(
        name=payload.name,
        description=payload.description,
        color_key=payload.color_key,
        mode="caption",
        styles=[VoiceStyleDef(**style.model_dump()) for style in payload.styles],
    )
    return voice_out_for_preset(state, preset)


@router.patch("/voices/{voice_id:path}", response_model=VoiceOut)
def update_voice(request: Request, voice_id: str, payload: VoiceUpdateRequest) -> VoiceOut:
    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    changes = payload.model_dump(exclude_none=True)

    try:
        preset = state.store.update(preset_id_from(voice_id), changes)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    except BackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, preset)


@router.post("/voices/{voice_id:path}/duplicate", response_model=VoiceOut, status_code=201)
def duplicate_voice(request: Request, voice_id: str) -> VoiceOut:
    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    try:
        preset = state.store.duplicate(preset_id_from(voice_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    except BackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return voice_out_for_preset(state, preset)


@router.delete("/voices/{voice_id:path}", status_code=204)
def delete_voice(request: Request, voice_id: str) -> None:
    state = engine_state(request)
    if state.store is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset_id = preset_id_from(voice_id)
    try:
        preset = state.store.get(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc

    assets = list(preset.reference_files)
    if preset.portrait_file:
        assets.append(preset.portrait_file)

    try:
        state.store.delete(preset_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    for name in assets:
        (voice_assets_dir() / name).unlink(missing_ok=True)
    icon_store.clear(voice_id)
    if state.service is not None:
        state.service.clear_cache()
