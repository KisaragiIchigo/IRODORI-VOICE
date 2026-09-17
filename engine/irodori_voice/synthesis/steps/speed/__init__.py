"""話速の伸縮を組み立てる部品。

    detect_pause_spans  … 間の位置を見つける（純粋関数）
    build_speed_plan    … 間と声へ倍率を配る（純粋関数）
    render_speed_plan   … 計画どおりに伸縮する
"""

from .build_speed_plan import SpeedBlock, SpeedPlan, build_speed_plan
from .detect_pause_spans import PauseSpan, detect_pause_spans
from .render_speed_plan import render_speed_plan

__all__ = [
    "PauseSpan",
    "SpeedBlock",
    "SpeedPlan",
    "build_speed_plan",
    "detect_pause_spans",
    "render_speed_plan",
]
