"""参照音声を持つシード話者の、表現を優先した生成設定。"""

from dataclasses import replace

from .reference import REFERENCE_SPEAKER_CFG
from .store import VoiceStyleDef


def apply_seed_expression_profile(style: VoiceStyleDef) -> VoiceStyleDef:
    """声のお手本・本文条件を保ち、採用済みの表現条件を設定する。

    生成回数とキャプションの効きは表現の担当なので、利用者が聴き比べて選んだ値
    （40 回・キャプション 5.0）をそのまま使う。

    参照音声の忠実さだけを 2.0 から REFERENCE_SPEAKER_CFG へ上げる。これは表現ではなく
    「誰の声か」を決める別の条件で、reference.py の実測が音質と声の近さの両方で最良と
    結論づけた値でもある。話者条件が緩いと短い区間で尺の予測が外れ、余った尺をモデルが
    言葉で埋めてしまうため、表現は落とさずにここだけを締める。
    """

    return replace(
        style,
        num_steps=40,
        cfg_scale_caption=5.0,
        cfg_scale_speaker=REFERENCE_SPEAKER_CFG,
    )
