"""話者のアイコンと立ち絵を生成する。

VOICEVOX エディタは ``speaker_info`` が返す icon / portrait を base64 の画像として
解釈する。空文字列を返すと "Unsupported image type" で落ちるため、必ず実体のある
画像を返す必要がある。

画像は持っていないので、話者の識別色から単純な図形を描いて返す。
色は project_style.json の palette.voice_chips と対応している。
"""

from __future__ import annotations

import base64
import io
from functools import lru_cache

# project_style.json の palette.voice_chips と同じ値。
VOICE_CHIP_COLORS: dict[str, tuple[int, int, int]] = {
    "shu": (226, 85, 58),
    "yamabuki": (224, 161, 58),
    "wakatake": (102, 176, 112),
    "asagi": (63, 164, 184),
    "rurikon": (90, 114, 201),
    "fuji": (154, 118, 208),
    "kobai": (221, 111, 149),
    "sumire": (124, 134, 168),
}

# 同じく palette の base_bg。
BACKGROUND = (13, 14, 18)

ICON_SIZE = 128
PORTRAIT_SIZE = (512, 512)

# 1x1 の透明 PNG。PIL が無い環境でも「画像として解釈できる」値を返すための最終手段。
_FALLBACK_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8"
    "DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


def _color(color_key: str) -> tuple[int, int, int]:
    return VOICE_CHIP_COLORS.get(color_key, VOICE_CHIP_COLORS["shu"])


@lru_cache(maxsize=64)
def icon_for(color_key: str) -> str:
    """話者一覧に並ぶ丸アイコン。識別色の同心円で描く。"""

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return _FALLBACK_PNG

    color = _color(color_key)
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.ellipse([0, 0, ICON_SIZE - 1, ICON_SIZE - 1], fill=BACKGROUND + (255,))
    inset = ICON_SIZE // 6
    draw.ellipse(
        [inset, inset, ICON_SIZE - 1 - inset, ICON_SIZE - 1 - inset],
        fill=color + (255,),
    )
    core = ICON_SIZE // 3
    draw.ellipse(
        [core, core, ICON_SIZE - 1 - core, ICON_SIZE - 1 - core],
        fill=BACKGROUND + (255,),
    )

    return _encode(image)


@lru_cache(maxsize=64)
def portrait_for(color_key: str) -> str:
    """話者選択時に表示される大きい画像。縦に流れる帯で描く。"""

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return _FALLBACK_PNG

    color = _color(color_key)
    width, height = PORTRAIT_SIZE
    image = Image.new("RGBA", PORTRAIT_SIZE, BACKGROUND + (255,))
    draw = ImageDraw.Draw(image)

    # 下へ向かって濃くなる帯。単調な塗りを避けつつ、色で話者を識別できるようにする。
    bands = 5
    for index in range(bands):
        ratio = index / float(bands)
        band_color = tuple(
            int(BACKGROUND[channel] + (color[channel] - BACKGROUND[channel]) * (0.25 + ratio * 0.75))
            for channel in range(3)
        )
        top = int(height * (0.42 + ratio * 0.11))
        draw.rectangle([0, top, width, top + int(height * 0.035)], fill=band_color + (255,))

    draw.ellipse(
        [width // 2 - 70, height // 2 - 180, width // 2 + 70, height // 2 - 40],
        fill=color + (255,),
    )

    return _encode(image)


def _encode(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")
