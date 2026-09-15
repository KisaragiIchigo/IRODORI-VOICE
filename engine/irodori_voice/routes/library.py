"""音声モデルライブラリの管理。"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..backends.sbv2 import irvm as irvm_pack
from ..backends.sbv2 import metadata as sbv2_metadata
from ..backends.sbv2 import sbv2_import
from ..paths import aivm_library_dir
from ..schemas import ModelOut, ModelSpeakerOut, VoiceStyleOut
from ..state import EngineState

router = APIRouter(prefix="/aivm", tags=["aivm"])

ALLOWED_SUFFIXES = {".aivm", ".aivmx", ".irvm"}
MAX_MODEL_BYTES = 2 * 1024**3


def _state(request: Request) -> EngineState:
    return request.app.state.engine


ONNX_NOTE = (
    "ONNX 形式のため合成には使えません。"
    "導入されている style-bert-vits2 は PyTorch 形式にのみ対応しています。"
    "同じ話者の PyTorch 形式を取り込むと使えるようになります。"
)


def _to_out(model: sbv2_metadata.InstalledModel) -> ModelOut:
    return ModelOut(
        uuid=model.uuid,
        name=model.name,
        description=model.description,
        creators=model.creators,
        license=model.license,
        model_architecture=model.model_architecture,
        model_format=model.model_format,
        version=model.version,
        speakers=[
            ModelSpeakerOut(
                uuid=speaker.uuid,
                name=speaker.name,
                local_id=speaker.local_id,
                styles=[
                    VoiceStyleOut(style_id=str(style.local_id), name=style.name)
                    for style in speaker.styles
                ],
            )
            for speaker in model.speakers
        ],
        usable=not model.is_onnx,
        note=ONNX_NOTE if model.is_onnx else None,
    )


@router.get("", response_model=list[ModelOut])
def list_models(request: Request) -> list[ModelOut]:
    state = _state(request)
    if state.aivm is None:
        return []
    state.aivm.refresh()
    return [_to_out(model) for model in state.aivm.installed_models()]


@router.post("/install", response_model=ModelOut, status_code=201)
async def install_model(request: Request, model: UploadFile = File(...)) -> ModelOut:
    """音声モデルをライブラリへ取り込む。

    受け取ったファイルは一時領域へ落としてから展開する。アップロード中の
    中断で壊れたファイルがライブラリに残らないようにするため。
    """

    state = _state(request)
    if state.aivm is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    suffix = Path(model.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"対応していない拡張子です: {suffix or '(拡張子なし)'}。"
                "対応する形式のファイルを指定してください。"
            ),
        )

    temp_dir = Path(tempfile.gettempdir()) / "irodori-voice-upload"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4().hex}{suffix}"

    written = 0
    try:
        with temp_path.open("wb") as handle:
            while chunk := await model.read(4 * 1024 * 1024):
                written += len(chunk)
                if written > MAX_MODEL_BYTES:
                    raise HTTPException(status_code=400, detail="モデルファイルが大きすぎます。")
                handle.write(chunk)

        try:
            if suffix == irvm_pack.IRVM_SUFFIX:
                installed = irvm_pack.install_irvm(temp_path)
            else:
                installed = sbv2_metadata.install(temp_path)
        except irvm_pack.IrvmError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except sbv2_metadata.ModelBackendUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=f"モデルファイルを読み取れませんでした: {exc}") from exc
        except Exception as exc:
            # 読み取りライブラリは独自の例外を投げるうえ、版によって API 名も変わる。
            # 捕まえ損ねると 500 になり、画面には「Internal Server Error」としか出ず、
            # 原因がエンジンのログにしか残らない。型ではなく内容を返す。
            raise HTTPException(
                status_code=400,
                detail=f"モデルファイルを取り込めませんでした: {type(exc).__name__}: {exc}",
            ) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    state.aivm.refresh()
    return _to_out(installed)


@router.post("/install-sbv2", response_model=ModelOut, status_code=201)
async def install_style_bert_vits2(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    model: UploadFile = File(...),
    config: UploadFile = File(...),
    style_vectors: UploadFile = File(...),
) -> ModelOut:
    """束ねられていない Style-Bert-VITS2 モデルを取り込む。

    配布されている学習済みモデルは、次の 3 点セットで配られることが多い。

        model.safetensors / config.json / style_vectors.npy

    取り込み後は束ねられたモデルと同じ扱いになり、話者一覧に並ぶ。
    """

    state = _state(request)
    if state.aivm is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    written = 0
    chunks: dict[str, bytes] = {}
    for label, upload in (
        ("model", model),
        ("config", config),
        ("style_vectors", style_vectors),
    ):
        data = await upload.read()
        written += len(data)
        if written > MAX_MODEL_BYTES:
            raise HTTPException(status_code=400, detail="モデルファイルが大きすぎます。")
        chunks[label] = data

    try:
        installed = sbv2_import.install_from_files(
            model_bytes=chunks["model"],
            config_bytes=chunks["config"],
            style_vectors_bytes=chunks["style_vectors"],
            display_name=name,
        )
    except sbv2_import.Sbv2ImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state.aivm.refresh()
    if state.service is not None:
        state.service.clear_cache()
    return _to_out(installed)


@router.post("/install-sbv2-folder", response_model=ModelOut, status_code=201)
def install_style_bert_vits2_folder(
    request: Request,
    directory: str,
    name: str | None = None,
) -> ModelOut:
    """ローカルのフォルダから Style-Bert-VITS2 モデルを取り込む。

    大きなモデルをアップロードせずに済むので、手元にフォルダがある場合はこちらが速い。
    """

    state = _state(request)
    if state.aivm is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    source = Path(directory).expanduser()
    try:
        installed = sbv2_import.install_from_directory(source, display_name=name)
    except sbv2_import.Sbv2ImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state.aivm.refresh()
    if state.service is not None:
        state.service.clear_cache()
    return _to_out(installed)


@router.delete("/{model_uuid}", status_code=204)
def uninstall_model(request: Request, model_uuid: str) -> None:
    state = _state(request)
    if state.aivm is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    target = aivm_library_dir() / model_uuid
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="指定されたモデルは登録されていません。")

    state.aivm.shutdown()
    shutil.rmtree(target, ignore_errors=True)
    state.aivm.refresh()
    if state.service is not None:
        state.service.clear_cache()
