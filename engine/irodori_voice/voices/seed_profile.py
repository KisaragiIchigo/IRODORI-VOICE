"""参照音声を持つシード話者の、表現を優先した生成設定。"""

from dataclasses import replace

from .store import VoiceStyleDef


def apply_seed_expression_profile(style: VoiceStyleDef) -> VoiceStyleDef:
    """声のお手本・本文条件を保ち、採用済みの表現条件を設定する。"""
    return replace(style, num_steps=40, cfg_scale_caption=5.0, cfg_scale_speaker=2.0)
