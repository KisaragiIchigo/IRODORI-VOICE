"""音声モデルの作成（IRVM の組み立て）。

ばらばらに配布された 4 点セットを 1 つの ``.irvm`` へまとめる。作ったものは
その場でライブラリへ取り込むか、ファイルとして受け取って配ることができる。

大きなファイルを扱うため、フォルダを指す経路も用意している。ブラウザから
数百 MB を送るより、エンジンが直接読むほうが速く終わる。
"""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from ..backends.sbv2 import irvm as irvm_pack
from ..schemas import ModelBuildOut
from ..state import EngineState

router = APIRouter(prefix="/models", tags=["models"])

# 重みは大きい。ONNX と Safetensors を両方積むことも想定して広めに取る。
MAX_BUILD_BYTES = 4 * 1024**3


def _state(request: Request) -> EngineState:
    return request.app.state.engine


def _to_out(manifest: dict, *, installed: bool, size_bytes: int) -> ModelBuildOut:
    contains = manifest.get("contains", {})
    speakers = manifest.get("speakers", [])
    return ModelBuildOut(
        uuid=str(manifest.get("uuid", "")),
        name=str(manifest.get("name", "")),
        model_architecture=str(manifest.get("model_architecture", "")),
        has_safetensors=bool(contains.get("safetensors")),
        has_onnx=bool(contains.get("onnx")),
        speaker_count=len(speakers),
        style_count=len(speakers[0].get("styles", [])) if speakers else 0,
        size_bytes=size_bytes,
        installed=installed,
        file_name=f"{manifest.get('name', 'model')}{irvm_pack.IRVM_SUFFIX}",
    )


async def _read_upload(upload: UploadFile | None, *, label: str, budget: list[int]) -> bytes | None:
    """アップロードを読み、全体の上限を超えたら弾く。"""

    if upload is None or not upload.filename:
        return None
    data = await upload.read()
    budget[0] += len(data)
    if budget[0] > MAX_BUILD_BYTES:
        raise HTTPException(status_code=400, detail=f"{label} を含めた合計が大きすぎます。")
    return data


@router.post("/build", status_code=201)
async def build_model(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    description: str = Form("", max_length=300),
    config: UploadFile = File(...),
    style_vectors: UploadFile = File(...),
    model: UploadFile | None = File(None),
    onnx: UploadFile | None = File(None),
    install: bool = Form(True),
) -> Response:
    """4 点セットから IRVM を組み立てる。

    ``install`` を立てるとライブラリへも取り込む。落とすと、作ったファイルを
    そのまま返すだけになる（配布用に持ち出したい場合）。

    本体は ZIP として返し、要約（``ModelBuildOut``）は ``X-Irodori-Model`` ヘッダへ
    base64 で載せる。作った直後にそのまま保存できるようにするため。
    """

    state = _state(request)
    budget = [0]

    config_bytes = await _read_upload(config, label="config.json", budget=budget)
    style_bytes = await _read_upload(style_vectors, label="スタイルベクトル", budget=budget)
    model_bytes = await _read_upload(model, label="学習済みモデル", budget=budget)
    onnx_bytes = await _read_upload(onnx, label="ONNX モデル", budget=budget)

    if config_bytes is None or style_bytes is None:
        raise HTTPException(
            status_code=400,
            detail="config.json とスタイルベクトル（style_vectors.npy）は必須です。",
        )

    try:
        payload, manifest = irvm_pack.build_irvm(
            name=name.strip(),
            config_bytes=config_bytes,
            style_vectors_bytes=style_bytes,
            safetensors_bytes=model_bytes,
            onnx_bytes=onnx_bytes,
            description=description.strip(),
        )
    except irvm_pack.IrvmError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    installed = False
    if install:
        target = irvm_pack.aivm_library_dir() / str(manifest["uuid"])
        target.mkdir(parents=True, exist_ok=True)
        temp = target / f"_build{irvm_pack.IRVM_SUFFIX}"
        temp.write_bytes(payload)
        try:
            irvm_pack.install_irvm(temp)
            installed = True
        except irvm_pack.IrvmError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            temp.unlink(missing_ok=True)
        if state.aivm is not None:
            state.aivm.refresh()
        if state.service is not None:
            state.service.clear_cache()

    out = _to_out(manifest, installed=installed, size_bytes=len(payload))
    # 本体はファイルとして返し、要約はヘッダへ載せる。作った直後に保存できるようにする。
    # HTTP ヘッダは latin-1 しか通らないため、日本語を含む要約は base64 にする。
    summary = base64.b64encode(out.model_dump_json().encode("utf-8")).decode("ascii")
    return Response(
        content=payload,
        status_code=201,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{manifest["uuid"]}{irvm_pack.IRVM_SUFFIX}"',
            "X-Irodori-Model": summary,
            "Cache-Control": "no-store",
        },
    )


@router.post("/build-from-folder", response_model=ModelBuildOut, status_code=201)
def build_from_folder(
    request: Request,
    directory: str,
    name: str | None = None,
) -> ModelBuildOut:
    """フォルダの中身をそのまま取り込む。

    ファイルを送らずに済むため、数百 MB の重みでも待たされない。IRVM を作らずに
    直接展開するので、配布用のファイルが要らない場合はこちらが速い。
    """

    state = _state(request)
    source = Path(directory).expanduser()

    try:
        installed = irvm_pack.install_from_directory(source, display_name=name)
    except irvm_pack.IrvmError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if state.aivm is not None:
        state.aivm.refresh()
    if state.service is not None:
        state.service.clear_cache()

    has_safetensors = (installed.directory / "model.safetensors").is_file()
    has_onnx = (installed.directory / "model.onnx").is_file()
    return ModelBuildOut(
        uuid=installed.uuid,
        name=installed.name,
        model_architecture=installed.model_architecture,
        has_safetensors=has_safetensors,
        has_onnx=has_onnx,
        speaker_count=len(installed.speakers),
        style_count=len(installed.speakers[0].styles) if installed.speakers else 0,
        size_bytes=sum(f.stat().st_size for f in installed.directory.iterdir() if f.is_file()),
        installed=True,
        file_name=f"{installed.name}{irvm_pack.IRVM_SUFFIX}",
    )
