"""アプリケーションが読み書きするディレクトリの単一情報源。

配布形態（開発実行 / PyInstaller onedir / システムインストール）に関わらず、
ユーザーデータはユーザープロファイル配下へ、同梱アセットはパッケージ配下へ解決する。
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

APP_DIR_NAME = "IRODORI-VOICE"


def _frozen_root() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


@lru_cache(maxsize=1)
def package_root() -> Path:
    """``irodori_voice`` パッケージ本体のディレクトリ。"""

    return Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def vendor_root() -> Path:
    """ベンダリングした Irodori-TTS 推論コードの親ディレクトリ。"""

    return package_root() / "vendor"


@lru_cache(maxsize=1)
def admin_dist_dir() -> Path | None:
    """管理画面のビルド成果物。見つからなければ None。

    onedir で固めた場合は実行ファイルの隣に ``admin/`` として展開される。
    ソースから動かす場合はリポジトリの ``admin/dist`` を見る。画面を
    ビルドしていない状態でもエンジンは動くべきなので、無ければ配信しない。
    """

    # 同梱データは onedir でも実行ファイルの隣ではなく _internal/ 配下へ展開される。
    # その位置は sys._MEIPASS が指すので、実行ファイルのパスからは組み立てない。
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        bundled = Path(bundle_root) / "admin"
        return bundled if (bundled / "index.html").is_file() else None

    # engine/irodori_voice/paths.py -> engine/irodori_voice -> engine -> リポジトリルート
    built = package_root().parent.parent / "admin" / "dist"
    return built if (built / "index.html").is_file() else None


@lru_cache(maxsize=1)
def user_data_root() -> Path:
    """設定・話者プリセット・音声ライブラリを置くユーザー領域。"""

    override = os.environ.get("IRODORI_VOICE_DATA_DIR")
    if override:
        root = Path(override).expanduser().resolve()
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        root = Path(base) / APP_DIR_NAME
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        root = Path(base) / APP_DIR_NAME

    root.mkdir(parents=True, exist_ok=True)
    return root


@lru_cache(maxsize=1)
def cache_root() -> Path:
    """再生成可能な中間物（参照 latent、合成結果）の置き場。"""

    override = os.environ.get("IRODORI_VOICE_CACHE_DIR")
    if override:
        root = Path(override).expanduser().resolve()
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        root = Path(base) / APP_DIR_NAME / "cache"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches" / APP_DIR_NAME
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
        root = Path(base) / APP_DIR_NAME

    root.mkdir(parents=True, exist_ok=True)
    return root


def voices_dir() -> Path:
    """話者プリセット（JSON）と参照音声の保管場所。"""

    path = user_data_root() / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path


def voice_assets_dir() -> Path:
    """プリセットに紐づく参照 wav と画像。"""

    path = voices_dir() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def voice_icons_dir() -> Path:
    """話者へ付けたアイコンの保管場所。

    プリセットのアセットとは分けている。アイコンは Irodori-TTS の話者にも
    取り込んだモデルの話者にも付けられるため、プリセットに紐づくものではない。
    """

    path = voices_dir() / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def aivm_library_dir() -> Path:
    """インストール済み音声モデルの保管場所。"""

    path = user_data_root() / "aivm"
    path.mkdir(parents=True, exist_ok=True)
    return path


def latent_cache_dir() -> Path:
    """参照音声を DACVAE latent へエンコードした結果のキャッシュ。"""

    path = cache_root() / "reference-latents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_cache_dir() -> Path:
    """合成済み wav のディスクキャッシュ。"""

    path = cache_root() / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return user_data_root() / "settings.json"


def frozen_bundle_root() -> Path | None:
    """PyInstaller 等で凍結された場合の実行ディレクトリ。"""

    return _frozen_root()
