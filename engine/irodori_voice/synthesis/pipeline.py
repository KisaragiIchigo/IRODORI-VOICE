"""合成パイプラインのオーケストレータ。

各 step を宣言順に呼ぶことだけに専念する。分割の判断、シードの導出、
波形の連結、形式変換はすべて steps/ 配下の関数が持つ。

    テキスト
      │  split_text_into_segments   長さで区間へ割る
      ▼
    シード
      │  resolve_seed_for_request   話者から安定した値を導出する
      ▼
    区間ごとのパラメータ
      │  build_segment_params       シードとスタイルを全区間で共有する
      ▼
    区間ごとの波形
      │  run_segments               順に合成する（キャッシュ経由）
      ▼
    1 本の波形
      │  join_segments              並べて繋ぐ
      ▼
    厚みの戻った波形
      │  apply_low_band_restore     痩せた低域だけ持ち上げる
      ▼
    話速の変わった波形
      │  apply_speed_samples        生成レートのまま伸縮
      ▼
    出力
         apply_output_format        レート変換・ステレオ化・ピーク保護
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..backends.base import SynthesisOutput, SynthesisParams
from .steps.apply_low_band_restore import LowBandPolicy, apply_low_band_restore
from .steps.apply_output_format import FormattedAudio, OutputFormat, apply_output_format
from .steps.apply_speed_scale import apply_speed_samples
from .steps.build_segment_params import build_segment_params
from .steps.join_segments import join_segments
from .steps.resolve_seed import resolve_seed_for_request
from .steps.run_segments import SegmentSynthesizer, run_segments
from .steps.split_text import (
    DEFAULT_MAX_CHARS,
    DEFAULT_TARGET_CHARS,
    split_text_into_segments,
)


@dataclass(frozen=True)
class SplitPolicy:
    """分割の方針。無効にすると 1 区間のまま合成する。"""

    enabled: bool = True
    target_chars: int = DEFAULT_TARGET_CHARS
    max_chars: int = DEFAULT_MAX_CHARS
    sentence_silence: float = 0.25
    clause_silence: float = 0.1


@dataclass
class PipelineResult:
    audio: FormattedAudio
    used_seed: int
    cached: bool
    segment_count: int
    stage_timings: list[tuple[str, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def synthesize_pipeline(
    params: SynthesisParams,
    *,
    synthesize_segment: SegmentSynthesizer,
    split: SplitPolicy = SplitPolicy(),
    output: OutputFormat = OutputFormat(),
    low_band: LowBandPolicy = LowBandPolicy(),
    speed_scale: float = 1.0,
) -> PipelineResult:
    """テキスト 1 件を合成し、wav まで仕上げて返す。"""

    segments = (
        split_text_into_segments(
            params.text,
            target_chars=split.target_chars,
            max_chars=split.max_chars,
            sentence_silence=split.sentence_silence,
            clause_silence=split.clause_silence,
        )
        if split.enabled
        else split_text_into_segments(params.text, max_chars=10**9)
    )
    if not segments:
        raise ValueError("合成するテキストがありません。")

    seed = resolve_seed_for_request(
        voice_id=params.voice_id,
        style_id=params.style_id,
        explicit_seed=params.seed,
    )

    segment_params = [
        build_segment_params(params, segment, seed=seed, total_segments=len(segments))
        for segment in segments
    ]

    outputs, cached = run_segments(segment_params, synthesize_segment)
    joined = join_segments(outputs)

    restored = apply_low_band_restore(
        joined.samples,
        sample_rate=joined.sample_rate,
        policy=low_band,
    )

    stretched = apply_speed_samples(
        restored.samples,
        sample_rate=joined.sample_rate,
        scale=speed_scale,
    )

    formatted = apply_output_format(
        stretched,
        source_rate=joined.sample_rate,
        output=output,
    )

    notes = list(joined.notes)
    if restored.applied_gain_db > 0.0:
        notes.append(
            f"info: 低域が薄かったため {restored.applied_gain_db:.1f}dB 持ち上げました"
            f"（1kHz 未満 {restored.measured_ratio * 100:.1f}%）。"
        )

    return PipelineResult(
        audio=formatted,
        # ここで導出した値は、話者がシードを持つ場合にバックエンドが上書きする。
        # 報告するのは実際に合成へ渡った値でなければ、シードを疑う手掛かりにならない。
        used_seed=joined.used_seed,
        cached=cached,
        segment_count=len(segments),
        stage_timings=joined.stage_timings,
        notes=notes,
    )


def describe_segments(
    text: str,
    *,
    split: SplitPolicy = SplitPolicy(),
) -> list[str]:
    """分割結果だけを確認する。設定画面や動作確認のための読み取り専用の経路。"""

    segments = split_text_into_segments(
        text,
        target_chars=split.target_chars,
        max_chars=split.max_chars,
    )
    return [segment.text for segment in segments]


__all__ = [
    "LowBandPolicy",
    "OutputFormat",
    "PipelineResult",
    "SplitPolicy",
    "SynthesisOutput",
    "apply_output_format",
    "describe_segments",
    "synthesize_pipeline",
]
