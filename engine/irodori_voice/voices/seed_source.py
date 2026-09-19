"""試聴と焼き付けで使うシード話者の条件を揃える。"""

from dataclasses import replace
import uuid

from ..backends.base import BackendError
from ..backends.irodori.backend import preset_id_from
from .store import VoicePreset, VoicePresetStore, VoiceStyleDef


def resolve_seed_source(store: VoicePresetStore, source_voice_id: str | None) -> VoicePreset | None:
    if source_voice_id is None:
        return None
    try:
        return store.get(preset_id_from(source_voice_id))
    except KeyError as exc:
        raise BackendError("元にするIRODORIの声が見つかりません。一覧を再読み込みしてください。") from exc


def build_seed_style(source: VoicePreset | None, caption: str | None) -> VoiceStyleDef:
    style = source.styles[0] if source else VoiceStyleDef(style_id="normal", name="ノーマル")
    return replace(style, style_id="normal", name="ノーマル", caption=caption or style.caption)


def create_seed_preset(
    store: VoicePresetStore, *, seed: int, caption: str | None,
    source_voice_id: str | None = None,
) -> VoicePreset:
    source = resolve_seed_source(store, source_voice_id)
    # 声質は入力シードから生成するため、元話者の参照音声・埋め込みは渡さない。
    return store.create(
        name=f"__seed_{uuid.uuid4().hex[:8]}",
        description="シード生成のための一時的な話者",
        color_key="shu",
        mode="caption",
        styles=[replace(build_seed_style(source, caption), num_steps=80, cfg_scale_text=2.0)],
        voice_seed=seed,
    )
