"""音声モデルファイルの読み取りとライブラリへの展開。

``.aivm`` は Safetensors、``.aivmx`` は ONNX の拡張仕様で、どちらもメタデータを
ファイル内部に抱えている。Style-Bert-VITS2 の ``TTSModel`` は
「モデル本体 / ハイパーパラメータ / スタイルベクトル」を別々の入力として受け取るため、
インストール時にこの 3 点へ展開しておく。拡張子の判定に依存せずに済み、
起動のたびにメタデータを読み直すコストも無くなる。
"""

from __future__ import annotations

import base64
import binascii
import json
import shutil
import uuid as uuid_module
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...paths import aivm_library_dir

MANIFEST_FILE = "manifest.json"
CONFIG_FILE = "config.json"
STYLE_VECTORS_FILE = "style_vectors.npy"
SAFETENSORS_MODEL = "model.safetensors"
ONNX_MODEL = "model.onnx"


class ModelBackendUnavailableError(RuntimeError):
    """aivmlib / style-bert-vits2 が導入されていない。"""


@dataclass(frozen=True)
class InstalledStyle:
    local_id: int
    name: str
    icon: str | None


@dataclass(frozen=True)
class InstalledSpeaker:
    uuid: str
    name: str
    local_id: int
    # マニフェストのアイコンを取り出したファイル。持たないモデルもある。
    icon_path: Path | None
    supported_languages: list[str]
    styles: list[InstalledStyle]


@dataclass(frozen=True)
class InstalledModel:
    uuid: str
    name: str
    description: str
    creators: list[str]
    license: str | None
    model_architecture: str
    model_format: str
    version: str
    directory: Path
    speakers: list[InstalledSpeaker]

    @property
    def model_path(self) -> Path:
        # Safetensors を優先する。IRVM は両方を同梱できるが、合成に使えるのは
        # Safetensors 側だけなので、ONNX があってもそちらへ倒してはならない。
        safetensors = self.directory / SAFETENSORS_MODEL
        return safetensors if safetensors.is_file() else self.directory / ONNX_MODEL

    @property
    def config_path(self) -> Path:
        return self.directory / CONFIG_FILE

    @property
    def style_vectors_path(self) -> Path:
        return self.directory / STYLE_VECTORS_FILE

    @property
    def is_onnx(self) -> bool:
        """合成に使えない（ONNX しか持たない）モデルかどうか。

        両方を同梱する IRVM では False になる。ONNX があることではなく、
        Safetensors が無いことが「合成できない」の条件。
        """

        if (self.directory / SAFETENSORS_MODEL).is_file():
            return False
        return (self.directory / ONNX_MODEL).is_file()


def model_reader_available() -> bool:
    try:
        import aivmlib  # noqa: F401
    except ImportError:
        return False
    return True


def style_bert_vits2_available() -> bool:
    try:
        import style_bert_vits2  # noqa: F401
    except ImportError:
        return False
    return True


def _manifest_to_json(manifest: Any) -> dict[str, Any]:
    # aivmlib の manifest は Pydantic モデル。バージョン差を吸収して dict 化する。
    if hasattr(manifest, "model_dump"):
        return json.loads(manifest.model_dump_json())
    if hasattr(manifest, "dict"):
        return manifest.dict()
    raise ModelBackendUnavailableError("aivmlib のマニフェスト形式を解釈できませんでした。")


def _hyper_parameters_to_json(hyper_parameters: Any) -> dict[str, Any]:
    if hasattr(hyper_parameters, "model_dump"):
        return json.loads(hyper_parameters.model_dump_json())
    if hasattr(hyper_parameters, "dict"):
        return hyper_parameters.dict()
    raise ModelBackendUnavailableError("aivmlib のハイパーパラメータ形式を解釈できませんでした。")


def install(source: Path) -> InstalledModel:
    """音声モデルファイルをライブラリへ展開する。"""

    if not model_reader_available():
        raise ModelBackendUnavailableError(
            "aivmlib が導入されていません。この形式を使うには "
            "`pip install aivmlib style-bert-vits2` を実行してください。"
        )

    import aivmlib

    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"ファイルが見つかりません: {source}")

    suffix = source.suffix.lower()
    with source.open("rb") as handle:
        if suffix == ".aivmx":
            metadata = aivmlib.read_aivmx_metadata(handle)
            is_onnx = True
        elif suffix == ".aivm":
            metadata = aivmlib.read_aivm_metadata(handle)
            is_onnx = False
        else:
            raise ValueError(
                f"対応していない拡張子です: {suffix}。.aivm または .aivmx を指定してください。"
            )

    manifest_json = _manifest_to_json(metadata.manifest)
    model_uuid = str(manifest_json.get("uuid"))
    if not model_uuid or model_uuid == "None":
        raise ValueError("マニフェストに UUID がありません。")

    target_dir = aivm_library_dir() / model_uuid
    target_dir.mkdir(parents=True, exist_ok=True)

    # モデル本体はそのままコピーする。中身は Safetensors / ONNX として妥当なファイル。
    #
    # ただし style-bert-vits2 の get_net_g は .pth / .pt / .safetensors しか受け付けず、
    # .onnx は ValueError になる。ONNX 推論に対応した派生ライブラリを使わない限り、
    # ONNX 形式は取り込めても合成できない。取り込み自体は許し、合成時に理由を伝える。
    model_name = ONNX_MODEL if is_onnx else SAFETENSORS_MODEL
    shutil.copy2(source, target_dir / model_name)

    (target_dir / CONFIG_FILE).write_text(
        json.dumps(_hyper_parameters_to_json(metadata.hyper_parameters), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target_dir / MANIFEST_FILE).write_text(
        json.dumps(manifest_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 同じモデルを入れ直したときに、前のアイコンが残らないようにする。
    for stale in target_dir.glob("speaker-*"):
        stale.unlink(missing_ok=True)

    if metadata.style_vectors:
        (target_dir / STYLE_VECTORS_FILE).write_bytes(metadata.style_vectors)
    elif not (target_dir / STYLE_VECTORS_FILE).is_file():
        raise ValueError(
            "モデルファイルにスタイルベクトルが含まれていません。"
            "Style-Bert-VITS2 の合成にはスタイルベクトルが必要です。"
        )

    return _read_installed(target_dir)


# マニフェストのアイコンとして受け付ける形式。data URI の image/ 以下と対応する。
_ICON_SUFFIXES = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp", "gif": ".gif"}


def _extract_icon(directory: Path, local_id: int, icon: Any) -> Path | None:
    """マニフェストのアイコン（data URI）をファイルとして取り出す。

    モデル自身がアイコンを抱えている。話者の画像を決めるところでは
    ファイルのパスだけを扱いたいので、ここで一度だけ実体にする。すでに
    あれば何もしないため、取り込み済みのモデルも次に一覧を読んだ時点で揃う。
    """

    if not isinstance(icon, str) or not icon.startswith("data:image/"):
        return None

    header, _, payload = icon.partition(",")
    subtype = header[len("data:image/") :].split(";", 1)[0].lower()
    suffix = _ICON_SUFFIXES.get(subtype)
    if suffix is None or not payload:
        return None

    path = directory / f"speaker-{local_id}{suffix}"
    if path.is_file():
        return path

    try:
        path.write_bytes(base64.b64decode(payload, validate=True))
    except (binascii.Error, ValueError, OSError):
        return None
    return path


def build_speakers_from_config(
    config: dict[str, Any],
    *,
    model_uuid: str,
    display_name: str,
    uuid_namespace: uuid_module.UUID,
) -> list[dict[str, Any]]:
    """config.json の spk2id / style2id から、マニフェストの話者定義を起こす。

    話者が 1 名だけのモデルでは、利用者が付けた名前を話者名にする。spk2id には
    学習時のデータセット名がそのまま残っていることが多く（例: TSUMUGI_JP）、
    モデル一覧と話者一覧で名前が食い違って探せなくなるため。複数話者のモデルは
    どれがどれか分からなくなるので、config 側の名前を残す。

    話者 UUID は config 側の名前から作る。表示名を変えたければモデルごと作り直す
    ことになり、その時点でモデル UUID が変わるため、ここへ表示名を混ぜる必要はない。
    """

    data = config.get("data", {})
    speakers_map: dict[str, int] = data.get("spk2id") or {display_name: 0}
    styles_map: dict[str, int] = data.get("style2id") or {"Neutral": 0}

    styles = [
        {"name": name, "icon": None, "local_id": int(local_id), "voice_samples": []}
        for name, local_id in sorted(styles_map.items(), key=lambda item: item[1])
    ]

    entries = sorted(speakers_map.items(), key=lambda item: item[1])
    single_speaker = len(entries) == 1

    return [
        {
            "name": display_name if single_speaker else name,
            "icon": None,
            "supported_languages": ["ja"],
            "uuid": str(uuid_module.uuid5(uuid_namespace, f"{model_uuid}:{name}")),
            "local_id": int(local_id),
            "styles": styles,
        }
        for name, local_id in entries
    ]


def _read_installed(directory: Path) -> InstalledModel:
    manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))

    speakers: list[InstalledSpeaker] = []
    for raw_speaker in manifest.get("speakers", []):
        styles = [
            InstalledStyle(
                local_id=int(raw_style.get("local_id", 0)),
                name=str(raw_style.get("name", "ノーマル")),
                icon=raw_style.get("icon"),
            )
            for raw_style in raw_speaker.get("styles", [])
        ]
        if not styles:
            styles = [InstalledStyle(local_id=0, name="ノーマル", icon=None)]
        speakers.append(
            InstalledSpeaker(
                uuid=str(raw_speaker.get("uuid")),
                name=str(raw_speaker.get("name", "名称未設定")),
                local_id=int(raw_speaker.get("local_id", 0)),
                icon_path=_extract_icon(
                    directory, int(raw_speaker.get("local_id", 0)), raw_speaker.get("icon")
                ),
                supported_languages=list(raw_speaker.get("supported_languages", ["ja"])),
                styles=styles,
            )
        )

    return InstalledModel(
        uuid=str(manifest.get("uuid")),
        name=str(manifest.get("name", "名称未設定")),
        description=str(manifest.get("description", "")),
        creators=list(manifest.get("creators", [])),
        license=manifest.get("license"),
        model_architecture=str(manifest.get("model_architecture", "Style-Bert-VITS2")),
        model_format=str(manifest.get("model_format", "Safetensors")),
        version=str(manifest.get("version", "1.0.0")),
        directory=directory,
        speakers=speakers,
    )


def list_installed() -> list[InstalledModel]:
    models: list[InstalledModel] = []
    for directory in sorted(aivm_library_dir().iterdir()):
        if not directory.is_dir() or not (directory / MANIFEST_FILE).is_file():
            continue
        try:
            models.append(_read_installed(directory))
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    return models


def uninstall(model_uuid: str) -> None:
    directory = aivm_library_dir() / model_uuid
    if directory.is_dir():
        shutil.rmtree(directory)
