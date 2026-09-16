"""声の出どころから話者を作る口。

シード値、手持ちの参照音声、取り込んだ音声モデル、話者埋め込みの 4 通り。
どれもプリセットを 1 つ作って返すところへ合流する。"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...backends.base import BackendError
from ...paths import voice_assets_dir
from ...schemas import VoiceCloneFromModelRequest, VoiceFromSeedRequest, VoiceOut
from ...voices import clone, seed_bake
from ...voices.icon_store import ALLOWED_ICON_SUFFIXES
from ...voices.store import VoiceStyleDef
from .shared import ALLOWED_AUDIO_SUFFIXES, engine_state, save_upload, voice_out_for_preset

router = APIRouter(tags=["voices"])


@router.post("/voices/from-seed", response_model=VoiceOut, status_code=201)
def create_voice_from_seed(request: Request, payload: VoiceFromSeedRequest) -> VoiceOut:
    """シード値を指定して話者を作る。

    そのシードの声を 1 本だけ合成し、参照音声として焼き付ける。参照を持たせないと、
    シードを固定しても行ごとに別人の声になる（理由は voices/seed_bake.py）。
    合成を挟むぶん、作成には数秒から十数秒かかる。
    """

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    try:
        preset = seed_bake.create_voice_from_seed(
            irodori=state.irodori,
            store=state.store,
            name=payload.name,
            seed=payload.seed,
            description=payload.description,
            color_key=payload.color_key,
            caption=(payload.caption or "").strip() or None,
            reference_text=payload.reference_text,
        )
    except BackendError as exc:
        raise HTTPException(
            status_code=503 if not exc.recoverable else 400,
            detail=str(exc),
        ) from exc

    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, preset)


@router.post("/voices/upload", response_model=VoiceOut, status_code=201)
async def create_voice_with_reference(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    description: str = Form("", max_length=300),
    color_key: str = Form("shu", max_length=40),
    caption: str = Form("", max_length=400),
    references: list[UploadFile] = File(...),
    portrait: UploadFile | None = File(None),
) -> VoiceOut:
    """参照音声から話者を作る。

    複数本まとめてアップロードでき、指定した順に連結して参照になる。
    v4-Small は短いクリップを複数与えた方が話者類似度が上がるため、この形にしている。
    """

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    if not references:
        raise HTTPException(status_code=400, detail="参照音声を 1 本以上指定してください。")
    if len(references) > 20:
        raise HTTPException(status_code=400, detail="参照音声は 20 本までです。")

    reference_files = [
        save_upload(upload, allowed=ALLOWED_AUDIO_SUFFIXES, prefix="ref") for upload in references
    ]
    portrait_file = (
        save_upload(portrait, allowed=ALLOWED_ICON_SUFFIXES, prefix="icon")
        if portrait is not None and portrait.filename
        else None
    )

    preset = state.store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=[
            VoiceStyleDef(
                style_id="normal",
                name="ノーマル",
                caption=caption.strip() or None,
            )
        ],
        reference_files=reference_files,
        portrait_file=portrait_file,
    )
    return voice_out_for_preset(state, preset)


@router.post("/voices/clone-from-aivm", response_model=VoiceOut, status_code=201)
def clone_voice_from_model(request: Request, payload: VoiceCloneFromModelRequest) -> VoiceOut:
    """取り込んだ話者の声を写した Irodori-TTS 話者を作る。

    取り込んだ話者で参照音声を合成し、それを声の手本として Irodori-TTS の話者に
    仕立てる。声の同一性はモデル側から、抑揚と間の取り方は Irodori-TTS から来る。

    参照音声の合成が伴うため、話者ひとつの作成に数秒から十数秒かかる。
    """

    state = engine_state(request)
    if state.store is None or state.irodori is None or state.aivm is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    availability = state.aivm.availability()
    if not availability.available:
        raise HTTPException(status_code=503, detail=availability.detail)

    try:
        preset = clone.clone_from_aivm(
            aivm=state.aivm,
            store=state.store,
            source_voice_id=payload.source_voice_id,
            source_style_id=payload.source_style_id,
            name=payload.name,
            description=payload.description,
            color_key=payload.color_key,
            reference_lines=tuple(payload.reference_lines) if payload.reference_lines else None,
            with_emotion_styles=payload.with_emotion_styles,
            normal_caption=payload.caption,
        )
    except BackendError as exc:
        raise HTTPException(
            status_code=503 if not exc.recoverable else 400,
            detail=str(exc),
        ) from exc

    if state.service is not None:
        state.service.clear_cache()
    return voice_out_for_preset(state, preset)


@router.post("/voices/import-embed", response_model=VoiceOut, status_code=201)
async def import_speaker_embedding(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    description: str = Form("", max_length=300),
    color_key: str = Form("shu", max_length=40),
    embedding: UploadFile = File(...),
) -> VoiceOut:
    """Speaker Inversion で学習した話者埋め込み（.speaker.safetensors）を取り込む。"""

    state = engine_state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    file_name = Path(embedding.filename or "").name
    if not file_name.endswith(".safetensors"):
        raise HTTPException(status_code=400, detail="拡張子が .safetensors のファイルを指定してください。")

    target_name = f"embed-{uuid.uuid4().hex[:12]}.safetensors"
    target_path = voice_assets_dir() / target_name
    with target_path.open("wb") as handle:
        shutil.copyfileobj(embedding.file, handle, length=1024 * 1024)

    preset = state.store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="embed",
        styles=[VoiceStyleDef(style_id="normal", name="ノーマル")],
        speaker_embed_file=target_name,
    )
    return voice_out_for_preset(state, preset)
