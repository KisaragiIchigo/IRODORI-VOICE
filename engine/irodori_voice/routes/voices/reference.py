"""話者に紐づく参照音声の管理。

追加・削除・一覧に加えて、シードの声を参照音声として焼き付ける口と、
どの話者からも参照されなくなったファイルの掃除を置く。"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ...backends.base import BackendError
from ...backends.irodori.backend import preset_id_from
from ...paths import voice_assets_dir
from ...schemas import VoiceBakeReferenceRequest, VoiceOut
from ...voices import seed_bake
from .shared import ALLOWED_AUDIO_SUFFIXES, engine_state, save_upload, voice_out_for_preset

router = APIRouter(tags=["voices"])


@router.post("/voices/{voice_id:path}/references", response_model=VoiceOut)
async def add_references(
    request: Request,
    voice_id: str,
    references: list[UploadFile] = File(...),
) -> VoiceOut:
    """既存の話者へ参照音声を追加する。"""

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset_id = preset_id_from(voice_id)
    try:
        preset = state.store.get(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    if preset.builtin:
        raise HTTPException(status_code=403, detail="同梱話者は編集できません。")

    added = [save_upload(upload, allowed=ALLOWED_AUDIO_SUFFIXES, prefix="ref") for upload in references]
    updated = state.store.update(
        preset_id,
        {
            "reference_files": preset.reference_files + added,
            "mode": "reference",
        },
    )
    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, updated)


@router.delete("/voices/{voice_id:path}/references/{index}", response_model=VoiceOut)
def remove_reference(request: Request, voice_id: str, index: int) -> VoiceOut:
    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset_id = preset_id_from(voice_id)
    try:
        preset = state.store.get(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    if preset.builtin:
        raise HTTPException(status_code=403, detail="同梱話者は編集できません。")
    if not 0 <= index < len(preset.reference_files):
        raise HTTPException(status_code=404, detail="指定された参照音声がありません。")

    removed = preset.reference_files[index]
    remaining = [name for i, name in enumerate(preset.reference_files) if i != index]
    updated = state.store.update(
        preset_id,
        {
            "reference_files": remaining,
            "mode": "reference" if remaining else "caption",
        },
    )
    (voice_assets_dir() / removed).unlink(missing_ok=True)
    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, updated)


@router.get("/voices/{voice_id:path}/references")
def list_references(request: Request, voice_id: str) -> list[dict[str, str | int]]:
    state = engine_state(request)
    if state.store is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    try:
        preset = state.store.get(preset_id_from(voice_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc

    entries: list[dict[str, str | int]] = []
    for index, name in enumerate(preset.reference_files):
        path = voice_assets_dir() / name
        entries.append(
            {
                "index": index,
                "file_name": name,
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return entries


@router.post("/voices/{voice_id:path}/bake-reference", response_model=VoiceOut)
def bake_voice_reference(
    request: Request, voice_id: str, payload: VoiceBakeReferenceRequest
) -> VoiceOut:
    """参照音声を持たない話者へ、あとから声を焼き付ける。

    作り直さずに声を固定するための入口。話者 ID が変わらないため、エディタが覚えている
    割り当ても、付けたアイコンもそのまま残る。合成を挟むぶん数秒から十数秒かかる。
    """

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    try:
        preset = seed_bake.bake_existing_voice(
            irodori=state.irodori,
            store=state.store,
            preset_id=preset_id_from(voice_id),
            reference_text=payload.reference_text,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BackendError as exc:
        raise HTTPException(
            status_code=503 if not exc.recoverable else 400,
            detail=str(exc),
        ) from exc

    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, preset)


@router.post("/voices/reset-assets", status_code=204)
def reset_orphan_assets(request: Request) -> None:
    """どのプリセットからも参照されていないアセットを片付ける。"""

    state = engine_state(request)
    if state.store is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    referenced: set[str] = set()
    for preset in state.store.list():
        referenced.update(preset.reference_files)
        if preset.portrait_file:
            referenced.add(preset.portrait_file)
        if preset.speaker_embed_file:
            referenced.add(preset.speaker_embed_file)

    for path in voice_assets_dir().iterdir():
        if path.is_file() and path.name not in referenced:
            path.unlink(missing_ok=True)
