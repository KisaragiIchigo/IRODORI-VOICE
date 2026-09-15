"""VOICEVOX 形式の話者 ID と、内部の voice_id / style_id の対応付け。

VOICEVOX の speaker は整数 ID で、外部ツールはこの数値を設定ファイルへ保存する。
そのため ID は「話者を追加しても既存の値が変わらない」ことが必須になる。
一覧の並び順で採番すると、話者を 1 つ足しただけで利用者側の設定が全部ずれる。

そこで voice_id と style_id のハッシュから決定的に生成する。
"""

from __future__ import annotations

import hashlib
import uuid

from ..backends.base import VoiceInfo
from .schemas import Speaker, SpeakerStyle

# VOICEVOX 本家の ID（0 〜 数千）と衝突しない範囲に寄せる。
_ID_NAMESPACE_BASE = 100_000
_ID_SPACE = 1_000_000

# UUID v5 の名前空間。同じ voice_id からは常に同じ UUID を作る。
_UUID_NAMESPACE = uuid.UUID("6f9c2e1a-5b3d-4e8f-9a7c-1d2e3f4a5b6c")


def style_id_for(voice_id: str, style_id: str | None) -> int:
    key = f"{voice_id}::{style_id or ''}"
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    return _ID_NAMESPACE_BASE + (int.from_bytes(digest[:4], "big") % _ID_SPACE)


def speaker_uuid_for(voice_id: str) -> str:
    return str(uuid.uuid5(_UUID_NAMESPACE, voice_id))


class SpeakerMap:
    """VOICEVOX の style id から内部の話者・スタイルを引くための対応表。"""

    def __init__(self, voices: list[VoiceInfo]) -> None:
        self._by_style_id: dict[int, tuple[str, str | None]] = {}
        self._speakers: list[Speaker] = []

        for voice in voices:
            styles: list[SpeakerStyle] = []
            for style in voice.styles or []:
                numeric_id = style_id_for(voice.voice_id, style.style_id)
                self._by_style_id[numeric_id] = (voice.voice_id, style.style_id)
                styles.append(SpeakerStyle(name=style.name, id=numeric_id))

            if not styles:
                numeric_id = style_id_for(voice.voice_id, None)
                self._by_style_id[numeric_id] = (voice.voice_id, None)
                styles.append(SpeakerStyle(name="ノーマル", id=numeric_id))

            self._speakers.append(
                Speaker(
                    name=voice.name,
                    speaker_uuid=speaker_uuid_for(voice.voice_id),
                    styles=styles,
                    version="0.1.0",
                )
            )

    @property
    def speakers(self) -> list[Speaker]:
        return self._speakers

    def resolve(self, numeric_id: int) -> tuple[str, str | None]:
        """VOICEVOX の speaker（= style id）から内部の識別子へ変換する。"""

        resolved = self._by_style_id.get(int(numeric_id))
        if resolved is None:
            raise KeyError(f"speaker={numeric_id} に対応する話者が見つかりません。")
        return resolved

    def find_by_uuid(self, speaker_uuid: str) -> Speaker | None:
        for speaker in self._speakers:
            if speaker.speaker_uuid == speaker_uuid:
                return speaker
        return None
