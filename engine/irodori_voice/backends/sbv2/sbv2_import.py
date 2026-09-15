"""束ねられていない Style-Bert-VITS2 モデルの取り込み。

配布されている学習済みモデルは、1 つに束ねられていないことも多い。
その場合は次の 3 点が揃ったフォルダとして配られる。

    model.safetensors   学習済みの重み（ファイル名は任意）
    config.json         ハイパーパラメータ。話者とスタイルの定義を含む
    style_vectors.npy   スタイルベクトル

モデルファイルと同じ置き場へ展開し、``manifest.json`` を自分で組み立てることで、
取り込み後は モデル と区別なく扱えるようにする。話者とスタイルは config.json の
``data.spk2id`` と ``data.style2id`` から起こす。
"""

from __future__ import annotations

import json
import shutil
import uuid as uuid_module
from pathlib import Path

from ...paths import aivm_library_dir
from .metadata import (
    CONFIG_FILE,
    MANIFEST_FILE,
    SAFETENSORS_MODEL,
    STYLE_VECTORS_FILE,
    InstalledModel,
    _read_installed,
    build_speakers_from_config,
)

# 同じフォルダから取り込み直したとき、同じ UUID になるようにする名前空間。
_UUID_NAMESPACE = uuid_module.UUID("3b7d1f52-8c4e-4a91-b6d3-7e2f9a1c4d08")


class Sbv2ImportError(RuntimeError):
    """取り込みに必要なファイルが揃っていない。"""


def _find_one(directory: Path, patterns: list[str], label: str) -> Path:
    for pattern in patterns:
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    raise Sbv2ImportError(
        f"{label} が {directory.name} に見つかりません。"
        " Style-Bert-VITS2 のモデルは、次の 3 つが同じフォルダに揃っている必要があります:"
        " model.safetensors（学習済みの重み。ファイル名は任意）、"
        " config.json（話者とスタイルの定義を含む設定）、"
        " style_vectors.npy（スタイルベクトル）。"
        " 学習時の model_assets/<キャラ名>/ をそのまま指定してください。"
    )


def _build_manifest(config: dict, *, model_uuid: str, fallback_name: str) -> dict:
    """config.json から モデル 相当のマニフェストを組み立てる。"""

    # 話者名は表示するモデル名に合わせる。config の model_name が空なら
    # 利用者が指定した名前（またはフォルダ名）が両方の元になる。
    model_name = config.get("model_name") or fallback_name

    return {
        "manifest_version": "1.0",
        "name": model_name,
        "description": "Style-Bert-VITS2 モデルとして取り込みました。",
        "creators": [],
        "license": None,
        "model_architecture": config.get("version", "Style-Bert-VITS2"),
        "model_format": "Safetensors",
        "uuid": model_uuid,
        "version": "1.0.0",
        "speakers": build_speakers_from_config(
            config,
            model_uuid=model_uuid,
            display_name=model_name,
            uuid_namespace=_UUID_NAMESPACE,
        ),
    }


def install_from_directory(source: Path, *, display_name: str | None = None) -> InstalledModel:
    """3 点セットのフォルダを取り込む。"""

    source = Path(source)
    if not source.is_dir():
        raise Sbv2ImportError(f"フォルダが見つかりません: {source}")

    model_file = _find_one(
        source,
        ["*.safetensors", "*.pth"],
        "モデルファイル（.safetensors）",
    )
    config_file = _find_one(source, ["config.json"], "設定ファイル（config.json）")
    style_file = _find_one(
        source,
        ["style_vectors.npy", "*.npy"],
        "スタイルベクトル（style_vectors.npy）",
    )

    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Sbv2ImportError(f"config.json を読み取れませんでした: {exc}") from exc

    fallback_name = display_name or source.name
    model_uuid = str(uuid_module.uuid5(_UUID_NAMESPACE, fallback_name))

    target = aivm_library_dir() / model_uuid
    target.mkdir(parents=True, exist_ok=True)

    shutil.copy2(model_file, target / SAFETENSORS_MODEL)
    shutil.copy2(style_file, target / STYLE_VECTORS_FILE)
    (target / CONFIG_FILE).write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / MANIFEST_FILE).write_text(
        json.dumps(
            _build_manifest(config, model_uuid=model_uuid, fallback_name=fallback_name),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return _read_installed(target)


def install_from_files(
    *,
    model_bytes: bytes,
    config_bytes: bytes,
    style_vectors_bytes: bytes,
    display_name: str,
) -> InstalledModel:
    """アップロードされた 3 ファイルから取り込む。"""

    try:
        config = json.loads(config_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Sbv2ImportError(f"config.json を読み取れませんでした: {exc}") from exc

    model_uuid = str(uuid_module.uuid5(_UUID_NAMESPACE, display_name))
    target = aivm_library_dir() / model_uuid
    target.mkdir(parents=True, exist_ok=True)

    (target / SAFETENSORS_MODEL).write_bytes(model_bytes)
    (target / STYLE_VECTORS_FILE).write_bytes(style_vectors_bytes)
    (target / CONFIG_FILE).write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / MANIFEST_FILE).write_text(
        json.dumps(
            _build_manifest(config, model_uuid=model_uuid, fallback_name=display_name),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return _read_installed(target)
