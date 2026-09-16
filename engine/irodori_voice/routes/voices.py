"""話者の一覧と、利用者が作るプリセットの管理。"""

from __future__ import annotations

import base64
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from .. import audio as audio_utils
from ..analysis import estimate_pitch
from ..backends.base import BackendError, SynthesisParams
from ..backends.irodori.backend import preset_id_from, voice_id_for
from ..paths import voice_assets_dir
from ..schemas import (
    SeedPreviewRequest,
    VoiceBakeReferenceRequest,
    VoiceCapabilitiesOut,
    VoiceCloneFromModelRequest,
    VoiceCreateRequest,
    VoiceFromSeedRequest,
    VoiceOut,
    VoiceStyleOut,
    VoiceUpdateRequest,
)
from ..state import EngineState
from ..voices import clone, seed_bake
from ..voices.icon_store import ALLOWED_ICON_SUFFIXES, MAX_ICON_BYTES, IconDecodeError, icon_store
from ..voices.store import VoiceStyleDef
from ..voicevox.speaker_image import icon_png, icon_source

router = APIRouter(tags=["voices"])

ALLOWED_AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}
MAX_UPLOAD_BYTES = 64 * 1024 * 1024


def _state(request: Request) -> EngineState:
    return request.app.state.engine


def _to_out(voice) -> VoiceOut:
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


def _voice_out_for_preset(state: EngineState, preset) -> VoiceOut:
    """保存した直後のプリセットを、話者一覧と同じ表現で返す。"""

    voice_id = voice_id_for(preset)
    return _to_out(next(v for v in state.irodori.list_voices() if v.voice_id == voice_id))


def _save_upload(upload: UploadFile, *, allowed: set[str], prefix: str) -> str:
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


@router.get("/voices", response_model=list[VoiceOut])
def list_voices(request: Request) -> list[VoiceOut]:
    state = _state(request)
    if state.registry is None:
        return []
    # モデル一覧と同じく、モデルライブラリを読み直してから返す。エンジンを通さずに
    # ライブラリのフォルダへモデルを置いた場合でも、一覧を開けばここで追いつく。
    if state.aivm is not None:
        state.aivm.refresh()
    return [_to_out(voice) for voice in state.registry.list_voices()]


def _find_voice(request: Request, voice_id: str):
    """話者を引き当てる。ここを通した ID だけを保管のキーに使う。"""

    state = _state(request)
    if state.registry is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    try:
        return state.registry.find_voice(voice_id)
    except BackendError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/voices/{voice_id:path}/icon")
def voice_icon(request: Request, voice_id: str) -> Response:
    """一覧に出るアイコン。付けていない話者も識別色の図形が返る。

    差し替えた直後に古い絵が残らないよう、保存させない。
    """

    voice = _find_voice(request, voice_id)
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

    voice = _find_voice(request, voice_id)

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

    return _to_out(voice)


@router.delete("/voices/{voice_id:path}/icon", response_model=VoiceOut)
def clear_voice_icon(request: Request, voice_id: str) -> VoiceOut:
    """付けたアイコンを外す。話者が元から持つ画像か識別色の図形へ戻る。"""

    voice = _find_voice(request, voice_id)
    icon_store.clear(voice.voice_id)
    return _to_out(voice)


@router.post("/voices", response_model=VoiceOut, status_code=201)
def create_voice(request: Request, payload: VoiceCreateRequest) -> VoiceOut:
    """参照音声を持たない話者（キャプション条件のみ）を作る。"""

    state = _state(request)
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
    return _voice_out_for_preset(state, preset)


@router.post("/voices/from-seed", response_model=VoiceOut, status_code=201)
def create_voice_from_seed(request: Request, payload: VoiceFromSeedRequest) -> VoiceOut:
    """シード値を指定して話者を作る。

    そのシードの声を 1 本だけ合成し、参照音声として焼き付ける。参照を持たせないと、
    シードを固定しても行ごとに別人の声になる（理由は voices/seed_bake.py）。
    合成を挟むぶん、作成には数秒から十数秒かかる。
    """

    state = _state(request)
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
    return _voice_out_for_preset(state, preset)


@router.post("/voices/preview-seed")
def preview_seed(request: Request, payload: SeedPreviewRequest) -> Response:
    """話者を作らずに、シード値の声を試す。

    合成には話者の定義が要るため、一時の話者を作って使い、終わったら必ず消す。
    保存されるものは何も残らない。

    本文は wav、声の高さの測定結果は ``X-Irodori-Preview`` ヘッダへ base64 で載せる。
    """

    state = _state(request)
    if state.store is None or state.irodori is None or state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset = state.store.create(
        name=f"__preview_{uuid.uuid4().hex[:8]}",
        description="試聴のための一時的な話者",
        color_key="shu",
        mode="caption",
        styles=[
            VoiceStyleDef(
                style_id="normal",
                name="ノーマル",
                caption=(payload.caption or "").strip() or None,
            )
        ],
        voice_seed=payload.seed,
    )

    try:
        # service.synthesize は (結果, キャッシュヒットか) を返す。
        result, _cached = state.service.synthesize(
            SynthesisParams(
                text=payload.text,
                voice_id=voice_id_for(preset),
                style_id="normal",
            )
        )
    except BackendError as exc:
        raise HTTPException(status_code=503 if not exc.recoverable else 400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # 合成が失敗しても一時の話者は残さない。
        state.store.delete(preset.preset_id)

    wav = audio_utils.encode_wav(result.samples, sample_rate=result.sample_rate)

    pitch = estimate_pitch(result.samples, result.sample_rate)
    meta = {
        "seed": payload.seed,
        "used_seed": result.used_seed,
        "sample_rate": result.sample_rate,
        "duration_seconds": round(len(result.samples) / result.sample_rate, 3),
        "pitch": pitch.to_dict() if pitch is not None else None,
    }
    encoded = base64.b64encode(json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode("ascii")

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"X-Irodori-Preview": encoded, "Cache-Control": "no-store"},
    )


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

    state = _state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    if not references:
        raise HTTPException(status_code=400, detail="参照音声を 1 本以上指定してください。")
    if len(references) > 20:
        raise HTTPException(status_code=400, detail="参照音声は 20 本までです。")

    reference_files = [
        _save_upload(upload, allowed=ALLOWED_AUDIO_SUFFIXES, prefix="ref") for upload in references
    ]
    portrait_file = (
        _save_upload(portrait, allowed=ALLOWED_ICON_SUFFIXES, prefix="icon")
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
    return _voice_out_for_preset(state, preset)


@router.post("/voices/clone-from-aivm", response_model=VoiceOut, status_code=201)
def clone_voice_from_model(request: Request, payload: VoiceCloneFromModelRequest) -> VoiceOut:
    """取り込んだ話者の声を写した Irodori-TTS 話者を作る。

    取り込んだ話者で参照音声を合成し、それを声の手本として Irodori-TTS の話者に
    仕立てる。声の同一性はモデル側から、抑揚と間の取り方は Irodori-TTS から来る。

    参照音声の合成が伴うため、話者ひとつの作成に数秒から十数秒かかる。
    """

    state = _state(request)
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
    return _voice_out_for_preset(state, preset)


@router.patch("/voices/{voice_id:path}", response_model=VoiceOut)
def update_voice(request: Request, voice_id: str, payload: VoiceUpdateRequest) -> VoiceOut:
    state = _state(request)
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
    return _voice_out_for_preset(state, preset)


@router.post("/voices/{voice_id:path}/bake-reference", response_model=VoiceOut)
def bake_voice_reference(
    request: Request, voice_id: str, payload: VoiceBakeReferenceRequest
) -> VoiceOut:
    """参照音声を持たない話者へ、あとから声を焼き付ける。

    作り直さずに声を固定するための入口。話者 ID が変わらないため、エディタが覚えている
    割り当ても、付けたアイコンもそのまま残る。合成を挟むぶん数秒から十数秒かかる。
    """

    state = _state(request)
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
    return _voice_out_for_preset(state, preset)


@router.post("/voices/{voice_id:path}/duplicate", response_model=VoiceOut, status_code=201)
def duplicate_voice(request: Request, voice_id: str) -> VoiceOut:
    state = _state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    try:
        preset = state.store.duplicate(preset_id_from(voice_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    except BackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _voice_out_for_preset(state, preset)


@router.delete("/voices/{voice_id:path}", status_code=204)
def delete_voice(request: Request, voice_id: str) -> None:
    state = _state(request)
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


@router.post("/voices/{voice_id:path}/references", response_model=VoiceOut)
async def add_references(
    request: Request,
    voice_id: str,
    references: list[UploadFile] = File(...),
) -> VoiceOut:
    """既存の話者へ参照音声を追加する。"""

    state = _state(request)
    if state.store is None or state.irodori is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset_id = preset_id_from(voice_id)
    try:
        preset = state.store.get(preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"話者 {voice_id} が見つかりません。") from exc
    if preset.builtin:
        raise HTTPException(status_code=403, detail="同梱話者は編集できません。")

    added = [_save_upload(upload, allowed=ALLOWED_AUDIO_SUFFIXES, prefix="ref") for upload in references]
    updated = state.store.update(
        preset_id,
        {
            "reference_files": preset.reference_files + added,
            "mode": "reference",
        },
    )
    if state.service is not None:
        state.service.clear_cache()
    return _voice_out_for_preset(state, updated)


@router.delete("/voices/{voice_id:path}/references/{index}", response_model=VoiceOut)
def remove_reference(request: Request, voice_id: str, index: int) -> VoiceOut:
    state = _state(request)
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
    return _voice_out_for_preset(state, updated)


@router.get("/voices/{voice_id:path}/references")
def list_references(request: Request, voice_id: str) -> list[dict[str, str | int]]:
    state = _state(request)
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


@router.post("/voices/reset-assets", status_code=204)
def reset_orphan_assets(request: Request) -> None:
    """どのプリセットからも参照されていないアセットを片付ける。"""

    state = _state(request)
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


@router.post("/voices/import-embed", response_model=VoiceOut, status_code=201)
async def import_speaker_embedding(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    description: str = Form("", max_length=300),
    color_key: str = Form("shu", max_length=40),
    embedding: UploadFile = File(...),
) -> VoiceOut:
    """Speaker Inversion で学習した話者埋め込み（.speaker.safetensors）を取り込む。"""

    state = _state(request)
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
    return _voice_out_for_preset(state, preset)
