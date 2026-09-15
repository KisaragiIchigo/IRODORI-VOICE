"""話者へ付けたアイコンの保管。

アイコンは話者の系統を問わず付けられるようにしたい。Irodori-TTS のプリセット
JSON へ持たせると取り込んだモデルの話者に付けられず、一覧の半分で効かない機能に
なるため、``voice_id`` をキーにした独立の保管にしている。

受け取った画像はその場で PNG へ正規化する。エディタは ``/speaker_info`` で
全話者ぶんのアイコンを base64 として受け取るため、原寸のまま抱えると起動の
たびに数十 MB が流れることになる。
"""

from __future__ import annotations

import io
from pathlib import Path

from ..paths import voice_icons_dir

# 受け付ける拡張子。中身は保存時に PIL で開き直すため、拡張子は入口の目安。
ALLOWED_ICON_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# 送信の上限。アイコン 1 枚にこれ以上は要らない。
MAX_ICON_BYTES = 16 * 1024 * 1024

# 保存する長辺。ここから一覧用の小さいアイコンと立ち絵の両方を作る。
STORED_MAX_EDGE = 512


class IconDecodeError(ValueError):
    """画像として読めなかった。呼び出し側が利用者へ理由を返すために使う。"""


def _key(voice_id: str) -> str:
    """voice_id をファイル名へ落とす。

    voice_id は ``irodori:user-xxxx`` や ``aivm:<uuid>:<local_id>`` の形。
    区切りの記号だけを置き換える。呼び出し側は実在する話者を引き当ててから
    ここへ来るため、任意の文字列は届かない。
    """

    return voice_id.replace(":", "-").replace("/", "-").replace("\\", "-")


class VoiceIconStore:
    """1 話者 1 ファイル。付いていなければファイルが無い、それだけの構造。"""

    def path_for(self, voice_id: str) -> Path | None:
        path = voice_icons_dir() / f"{_key(voice_id)}.png"
        return path if path.is_file() else None

    def save(self, voice_id: str, data: bytes) -> Path:
        """画像を正規化して保存する。読めない画像は ``IconDecodeError``。"""

        try:
            from PIL import Image, ImageOps
        except ImportError as exc:  # pragma: no cover - 同梱環境では起きない
            raise IconDecodeError(
                "画像を扱うライブラリ（Pillow）が見つかりません。"
                "`pip install pillow` を実行してください。"
            ) from exc

        try:
            with Image.open(io.BytesIO(data)) as source:
                # スマートフォンの写真は向きを EXIF に持つ。読み捨てると横倒しになる。
                image = ImageOps.exif_transpose(source)
                image = image.convert("RGBA")
                image.thumbnail((STORED_MAX_EDGE, STORED_MAX_EDGE), Image.LANCZOS)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG", optimize=True)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise IconDecodeError(
                "画像として読み取れませんでした。PNG / JPEG / WebP のいずれかを指定してください。"
            ) from exc

        path = voice_icons_dir() / f"{_key(voice_id)}.png"
        tmp = path.with_suffix(".png.tmp")
        tmp.write_bytes(buffer.getvalue())
        tmp.replace(path)
        return path

    def clear(self, voice_id: str) -> bool:
        """外したかどうかを返す。付いていなければ False。"""

        path = voice_icons_dir() / f"{_key(voice_id)}.png"
        if not path.is_file():
            return False
        path.unlink(missing_ok=True)
        return True


# エンジン全体で 1 つ。話者 API と /speaker_info の両方から参照する。
icon_store = VoiceIconStore()
