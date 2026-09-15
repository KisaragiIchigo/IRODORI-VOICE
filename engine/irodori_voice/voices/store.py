"""話者プリセットの型と永続化。

VOICEVOX の「話者 > スタイル」構造を Irodori-TTS の条件付けに対応させている。

    話者  = 声の同一性     -> 参照音声 / 話者埋め込み / キャプションのみ
    スタイル = 喋り方の指定 -> キャプション文とサンプリング既定値

こうしておくと、利用者は VOICEVOX と同じ手つきのまま、内部では v4-Small の
3 系統条件付け（テキスト / 参照音声 / キャプション）をそのまま使える。
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..paths import voice_assets_dir, voices_dir

VoiceMode = Literal["reference", "caption", "embed"]

PRESET_FILE_SUFFIX = ".voice.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class VoiceStyleDef:
    style_id: str
    name: str
    caption: str | None = None
    # 読み上げテキストの先頭へ付ける注釈絵文字。Irodori-TTS はこれを表現の指示として
    # 解釈する（duration の特徴量にもテキスト条件にも乗るため、キャプションより強く効く）。
    # 使えるのは vendor/irodori_tts/duration.py の ALLOWED_ANNOTATION_EMOJIS にある記号だけ。
    emoji: str | None = None
    duration_scale: float = 1.0
    cfg_scale_text: float = 3.0
    cfg_scale_caption: float = 3.0
    cfg_scale_speaker: float = 5.0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> VoiceStyleDef:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known})


@dataclass
class VoicePreset:
    preset_id: str
    name: str
    description: str
    color_key: str
    mode: VoiceMode
    styles: list[VoiceStyleDef]
    reference_files: list[str] = field(default_factory=list)
    speaker_embed_file: str | None = None
    # 参照音声を持たない話者の声を固定する値。None なら話者 ID から導出する。
    voice_seed: int | None = None
    portrait_file: str | None = None
    builtin: bool = False
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["styles"] = [style.to_json() for style in self.styles]
        return payload

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> VoicePreset:
        known = set(cls.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in known}
        filtered["styles"] = [VoiceStyleDef.from_json(s) for s in raw.get("styles", [])]
        return cls(**filtered)

    def style(self, style_id: str | None) -> VoiceStyleDef:
        if style_id is None:
            return self.styles[0]
        for candidate in self.styles:
            if candidate.style_id == style_id:
                return candidate
        raise KeyError(f"スタイル {style_id} は話者 {self.preset_id} に存在しません。")

    def reference_paths(self) -> list[str]:
        root = voice_assets_dir()
        return [str(root / name) for name in self.reference_files]

    def speaker_embed_path(self) -> str | None:
        if self.speaker_embed_file is None:
            return None
        return str(voice_assets_dir() / self.speaker_embed_file)

    def portrait_path(self) -> str | None:
        if self.portrait_file is None:
            return None
        return str(voice_assets_dir() / self.portrait_file)


class VoicePresetStore:
    """プリセットをファイル 1 つ 1 話者で永続化する。

    ユーザーが追加した話者は削除・編集できるが、同梱プリセットは上書き保存しない。
    起動のたびに同梱定義を読み直すことで、アプリ更新時に既定話者を差し替えられる。
    """

    def __init__(self, builtin: list[VoicePreset]) -> None:
        self._lock = threading.RLock()
        self._root = voices_dir()
        self._builtin = {preset.preset_id: preset for preset in builtin}
        self._user: dict[str, VoicePreset] = {}
        self._load_user_presets()

    def _load_user_presets(self) -> None:
        for path in sorted(self._root.glob(f"*{PRESET_FILE_SUFFIX}")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                preset = VoicePreset.from_json(raw)
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                continue
            preset.builtin = False
            self._user[preset.preset_id] = preset

    def _path_for(self, preset_id: str) -> Path:
        return self._root / f"{preset_id}{PRESET_FILE_SUFFIX}"

    def list(self) -> list[VoicePreset]:
        with self._lock:
            return list(self._builtin.values()) + list(self._user.values())

    def get(self, preset_id: str) -> VoicePreset:
        with self._lock:
            if preset_id in self._user:
                return self._user[preset_id]
            if preset_id in self._builtin:
                return self._builtin[preset_id]
        raise KeyError(f"話者 {preset_id} は登録されていません。")

    def create(
        self,
        *,
        name: str,
        description: str,
        color_key: str,
        mode: VoiceMode,
        styles: list[VoiceStyleDef],
        reference_files: list[str] | None = None,
        speaker_embed_file: str | None = None,
        portrait_file: str | None = None,
        voice_seed: int | None = None,
    ) -> VoicePreset:
        preset = VoicePreset(
            preset_id=f"user-{uuid.uuid4().hex[:12]}",
            name=name,
            description=description,
            color_key=color_key,
            mode=mode,
            styles=styles,
            reference_files=list(reference_files or []),
            speaker_embed_file=speaker_embed_file,
            portrait_file=portrait_file,
            voice_seed=voice_seed,
        )
        with self._lock:
            self._user[preset.preset_id] = preset
            self._persist(preset)
        return preset

    def update(self, preset_id: str, changes: dict[str, Any]) -> VoicePreset:
        with self._lock:
            if preset_id in self._builtin:
                raise PermissionError("同梱話者は編集できません。複製してから変更してください。")
            preset = self._user[preset_id]
            for key, value in changes.items():
                if key in ("preset_id", "builtin", "created_at"):
                    continue
                if key == "styles":
                    preset.styles = [VoiceStyleDef.from_json(s) for s in value]
                elif hasattr(preset, key):
                    setattr(preset, key, value)
            preset.updated_at = _now()
            self._persist(preset)
            return preset

    def duplicate(self, preset_id: str, *, name: str | None = None) -> VoicePreset:
        source = self.get(preset_id)
        return self.create(
            name=name or f"{source.name} のコピー",
            description=source.description,
            color_key=source.color_key,
            mode=source.mode,
            styles=[VoiceStyleDef.from_json(s.to_json()) for s in source.styles],
            reference_files=list(source.reference_files),
            speaker_embed_file=source.speaker_embed_file,
            portrait_file=source.portrait_file,
            voice_seed=source.voice_seed,
        )

    def delete(self, preset_id: str) -> None:
        with self._lock:
            if preset_id in self._builtin:
                raise PermissionError("同梱話者は削除できません。")
            self._user.pop(preset_id, None)
            self._path_for(preset_id).unlink(missing_ok=True)

    def _persist(self, preset: VoicePreset) -> None:
        path = self._path_for(preset.preset_id)
        path.write_text(
            json.dumps(preset.to_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
