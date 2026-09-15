"""話者の画像を決める。

``/speaker_info`` が返すアイコンと立ち絵は、次の順に決まる。

  1. 利用者がその話者へ付けたアイコン（``voices/icon_store``）
  2. 話者そのものが持っている画像（モデルのマニフェストのアイコン、参照音声と
     一緒に取り込んだ画像）
  3. どちらも無ければ識別色から描いた図形（``portrait``）

画像の読み込みは 1 と 2 のときだけ起きる。エディタは一覧を開くたびに全話者を
問い合わせるため、ファイルの更新時刻と大きさごと記憶して 2 回目以降は作り直さない。
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..backends.base import VoiceInfo
from ..voices.icon_store import icon_store
from .portrait import icon_for, portrait_for

IconSource = Literal["custom", "model", "generated"]

# 一覧に並ぶ小さいアイコン。エディタの表示は 2rem なので、倍密度で足りる。
ICON_EDGE = 128

# 話者を選んだときに出る画像。長辺をここまでに収める。
PORTRAIT_MAX_EDGE = 512

# 縦長の画像からアイコン用の正方形を切り出すときの上寄せ量。人物は上半分に
# 写るため、中央で切ると顔が外れる。
ICON_CROP_TOP_RATIO = 0.18


def _stamp(path: Path) -> tuple[int, int]:
    """作り直しの判定に使う印。

    更新時刻だけでは足りない。Windows のタイムスタンプは刻みが粗く、続けて
    差し替えたときに同じ値になることがある。大きさも合わせて見る。
    """

    info = path.stat()
    return info.st_mtime_ns, info.st_size


def source_of(voice: VoiceInfo) -> tuple[Path | None, IconSource]:
    """使う画像と、その出どころ。"""

    custom = icon_store.path_for(voice.voice_id)
    if custom is not None:
        return custom, "custom"
    if voice.portrait_path is not None and Path(voice.portrait_path).is_file():
        return Path(voice.portrait_path), "model"
    return None, "generated"


def icon_source(voice: VoiceInfo) -> IconSource:
    return source_of(voice)[1]


def icon_base64(voice: VoiceInfo) -> str:
    path, _ = source_of(voice)
    if path is not None:
        rendered = _render_icon(str(path), _stamp(path))
        if rendered is not None:
            return rendered
    return icon_for(voice.color_key)


def portrait_base64(voice: VoiceInfo) -> str:
    path, _ = source_of(voice)
    if path is not None:
        rendered = _render_portrait(str(path), _stamp(path))
        if rendered is not None:
            return rendered
    return portrait_for(voice.color_key)


def icon_png(voice: VoiceInfo) -> bytes:
    """管理画面へそのまま返すための PNG。生成したものも含めて必ず実体を返す。"""

    return base64.b64decode(icon_base64(voice))


@lru_cache(maxsize=128)
def _render_icon(path: str, stamp: tuple[int, int]) -> str | None:
    def shape(image, resample):
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (
            int((height - side) * ICON_CROP_TOP_RATIO)
            if height > width
            else (height - side) // 2
        )
        cropped = image.crop((left, top, left + side, top + side))
        return cropped.resize((ICON_EDGE, ICON_EDGE), resample)

    return _render(path, shape)


@lru_cache(maxsize=128)
def _render_portrait(path: str, stamp: tuple[int, int]) -> str | None:
    def shape(image, resample):
        image.thumbnail((PORTRAIT_MAX_EDGE, PORTRAIT_MAX_EDGE), resample)
        return image

    return _render(path, shape)


def _render(path: str, shape) -> str | None:
    """画像を読んで整形し、base64 の PNG にする。

    読めなかったときは None を返し、呼び出し側で識別色の図形へ落とす。
    取り込みのときに正規化しているので通常は起きないが、ファイルが外から
    差し替えられていることはある。
    """

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
            image = shape(image, Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None

    return base64.b64encode(buffer.getvalue()).decode("ascii")
