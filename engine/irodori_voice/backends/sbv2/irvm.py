"""IRVM（IRODORI-VOICE Model）の作成と取り込み。

音声モデルは通常、次の 4 つに分かれて配布される。

    model.safetensors   学習済みの重み（PyTorch 推論で使う）
    model.onnx          ONNX へ書き出した重み（ONNX 推論で使う）
    config.json         ハイパーパラメータ。話者とスタイルの定義を含む
    style_vectors.npy   スタイルベクトル

ばらばらのまま受け渡すと、どれか 1 つ欠けた状態で持ち込まれて「取り込めない」に
なりやすい。IRVM はこの 4 点を 1 つのファイルへまとめた入れ物で、中身は ZIP。
拡張子を見ただけで扱いが決まり、欠品はここで弾ける。

メタデータへ manifest を埋める方式と違って ZIP にしたのは、
ONNX と Safetensors を同時に入れられるようにするため。取り込み後は同じ
置き場へ展開するので、以降の扱いは変わらない。
"""

from __future__ import annotations

import io
import json
import shutil
import uuid as uuid_module
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ...paths import aivm_library_dir
from .metadata import (
    CONFIG_FILE,
    MANIFEST_FILE,
    ONNX_MODEL,
    SAFETENSORS_MODEL,
    STYLE_VECTORS_FILE,
    InstalledModel,
    _read_installed,
    build_speakers_from_config,
)

IRVM_SUFFIX = ".irvm"

# 入れ物の形式。読み込み側が中身を判別するために manifest へ書く。
IRVM_FORMAT = "irvm"
IRVM_FORMAT_VERSION = "1.0"

# 同じ名前から作り直したとき、同じ UUID になるようにする名前空間。
_UUID_NAMESPACE = uuid_module.UUID("6c1f2a83-5d47-4b90-9e35-1a8c7f4d20b6")


class IrvmError(RuntimeError):
    """IRVM の作成や取り込みに必要なものが足りない。"""


def build_manifest(
    config: dict,
    *,
    name: str,
    description: str = "",
    creators: list[str] | None = None,
    license_text: str | None = None,
    has_safetensors: bool = False,
    has_onnx: bool = False,
) -> dict:
    """IRVM の manifest を組み立てる。

    既存のマニフェストと同じ形を保ちつつ、入れ物の形式と同梱物を足す。
    取り込み後は同じ読み取り経路を通るため、形を揃えておく必要がある。
    """

    model_uuid = str(uuid_module.uuid5(_UUID_NAMESPACE, name))
    return {
        "manifest_version": "1.0",
        "format": IRVM_FORMAT,
        "format_version": IRVM_FORMAT_VERSION,
        "name": name,
        "description": description,
        "creators": list(creators or []),
        "license": license_text,
        "model_architecture": config.get("version", "Style-Bert-VITS2"),
        # 合成に使うのは Safetensors 側。ONNX は同梱しても現状は推論に使わない。
        "model_format": "Safetensors" if has_safetensors else "ONNX",
        "contains": {"safetensors": has_safetensors, "onnx": has_onnx},
        "uuid": model_uuid,
        "version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "speakers": build_speakers_from_config(
            config,
            model_uuid=model_uuid,
            display_name=name,
            uuid_namespace=_UUID_NAMESPACE,
        ),
    }


def build_irvm(
    *,
    name: str,
    config_bytes: bytes,
    style_vectors_bytes: bytes,
    safetensors_bytes: bytes | None = None,
    onnx_bytes: bytes | None = None,
    description: str = "",
    creators: list[str] | None = None,
    license_text: str | None = None,
) -> tuple[bytes, dict]:
    """4 点セットから IRVM を作る。ファイルのバイト列と manifest を返す。

    重みは Safetensors と ONNX のどちらか一方でも作れる。両方入れておくと、
    PyTorch 推論と ONNX 推論のどちらにも配れる 1 ファイルになる。
    """

    if safetensors_bytes is None and onnx_bytes is None:
        raise IrvmError(
            "学習済みモデル（.safetensors）と ONNX モデル（.onnx）の"
            "少なくとも一方が必要です。"
        )

    try:
        config = json.loads(config_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IrvmError(f"config.json を読み取れませんでした: {exc}") from exc

    if not style_vectors_bytes:
        raise IrvmError("スタイルベクトル（style_vectors.npy）が空です。")

    manifest = build_manifest(
        config,
        name=name,
        description=description,
        creators=creators,
        license_text=license_text,
        has_safetensors=safetensors_bytes is not None,
        has_onnx=onnx_bytes is not None,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(CONFIG_FILE, json.dumps(config, ensure_ascii=False, indent=2))
        archive.writestr(STYLE_VECTORS_FILE, style_vectors_bytes)
        if safetensors_bytes is not None:
            archive.writestr(SAFETENSORS_MODEL, safetensors_bytes)
        if onnx_bytes is not None:
            archive.writestr(ONNX_MODEL, onnx_bytes)

    return buffer.getvalue(), manifest


def install_irvm(source: Path) -> InstalledModel:
    """IRVM をライブラリへ展開する。

    展開先は ``<ライブラリ>/<UUID>/`` で、中のファイル名も揃える。
    取り込んだ後は形式の違いを意識せずに扱える。
    """

    source = Path(source)
    if not source.is_file():
        raise IrvmError(f"ファイルが見つかりません: {source}")

    try:
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
            missing = [
                item
                for item in (MANIFEST_FILE, CONFIG_FILE, STYLE_VECTORS_FILE)
                if item not in names
            ]
            if missing:
                raise IrvmError(f"IRVM に必要なファイルがありません: {', '.join(missing)}")
            if SAFETENSORS_MODEL not in names and ONNX_MODEL not in names:
                raise IrvmError("IRVM にモデル本体が入っていません。")

            manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8"))
            model_uuid = str(manifest.get("uuid") or "")
            if not model_uuid:
                raise IrvmError("IRVM のマニフェストに UUID がありません。")

            target = aivm_library_dir() / model_uuid
            target.mkdir(parents=True, exist_ok=True)
            for item in (MANIFEST_FILE, CONFIG_FILE, STYLE_VECTORS_FILE, SAFETENSORS_MODEL, ONNX_MODEL):
                if item in names:
                    (target / item).write_bytes(archive.read(item))
    except zipfile.BadZipFile as exc:
        raise IrvmError(f"IRVM を開けませんでした（壊れているようです）: {exc}") from exc

    return _read_installed(target)


def install_from_directory(source: Path, *, display_name: str | None = None) -> InstalledModel:
    """4 点セットが入ったフォルダを、IRVM を経由せずに直接取り込む。

    大きなモデルを ZIP へ固める往復を省ける。中身の判定は build_irvm と揃える。
    """

    source = Path(source)
    if not source.is_dir():
        raise IrvmError(f"フォルダが見つかりません: {source}")

    def _find(patterns: list[str]) -> Path | None:
        for pattern in patterns:
            matches = sorted(source.glob(pattern))
            if matches:
                return matches[0]
        return None

    config_file = _find(["config.json"])
    style_file = _find(["style_vectors.npy", "*.npy"])
    safetensors_file = _find(["*.safetensors", "*.pth"])
    onnx_file = _find(["*.onnx"])

    missing: list[str] = []
    if config_file is None:
        missing.append("config.json")
    if style_file is None:
        missing.append("style_vectors.npy")
    if safetensors_file is None and onnx_file is None:
        missing.append("model.safetensors または model.onnx")
    if missing:
        raise IrvmError(f"{source.name} に次のファイルがありません: {', '.join(missing)}")

    assert config_file is not None and style_file is not None  # 上で確認済み
    config = json.loads(config_file.read_text(encoding="utf-8"))
    name = display_name or source.name
    manifest = build_manifest(
        config,
        name=name,
        has_safetensors=safetensors_file is not None,
        has_onnx=onnx_file is not None,
    )

    target = aivm_library_dir() / str(manifest["uuid"])
    target.mkdir(parents=True, exist_ok=True)
    (target / MANIFEST_FILE).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / CONFIG_FILE).write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy2(style_file, target / STYLE_VECTORS_FILE)
    if safetensors_file is not None:
        shutil.copy2(safetensors_file, target / SAFETENSORS_MODEL)
    if onnx_file is not None:
        shutil.copy2(onnx_file, target / ONNX_MODEL)

    return _read_installed(target)
