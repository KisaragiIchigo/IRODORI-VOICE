"""取り込んだ話者の声を Irodori-TTS の参照音声として取り込む。

Style-Bert-VITS2 は声の同一性を強く保つ代わりに、喋り方は学習データの
範囲に収まる。Irodori-TTS は参照音声から声の同一性だけを受け取り、抑揚と間は
自前の条件付けで決める。両者を繋ぐと「モデルの声で、Irodori-TTS の喋り方」になる。

参照音声はこの層で合成して保存する。エディタを経由させると同じ波形が 2 度
ネットワークを通るため、バックエンドを直接呼んで numpy のまま扱う。
"""

from __future__ import annotations

from .. import audio as audio_utils
from ..backends.sbv2.backend import Sbv2Backend
from ..backends.base import BackendError, SynthesisParams
from .expression_styles import build_expression_styles
from .reference import (
    REFERENCE_CAPTION_CFG,
    REFERENCE_NUM_STEPS,
    REFERENCE_SPEAKER_CFG,
    save_reference_wavs,
)
from .store import VoicePreset, VoicePresetStore, VoiceStyleDef

# 参照音声の既定文。母音・撥音・促音・拗音が偏らないように選んである。
# 声の同一性を掴ませるのが目的なので、内容そのものに意味は無い。
REFERENCE_LINES: tuple[str, ...] = (
    "こんにちは。今日はいい天気ですね。お散歩にちょうどいい陽気だと思います。",
    "新しい機能の説明をします。設定の画面から、音量や話す速さを変えられます。",
    "ありがとうございました。またのご利用を、心よりお待ちしております。",
    "東京特許許可局の許可を受けて、朝の新聞をゆっくり読み上げました。",
)

# Irodori-TTS 側が参照として受け取れる長さの上限。これを超えた分は捨てられるため、
# 無駄なファイルを残さないよう合成の段階で打ち切る。
MAX_REFERENCE_SECONDS = 30.0


def _synthesize_clips(
    aivm: Sbv2Backend,
    *,
    source_voice_id: str,
    source_style_id: str | None,
    lines: tuple[str, ...],
) -> list[tuple[bytes, float]]:
    """参照用のクリップを合成する。wav のバイト列と長さの組を返す。

    上限に達した時点で打ち切る。残りの行を合成しても Irodori-TTS 側で捨てられる。
    """

    clips: list[tuple[bytes, float]] = []
    total_seconds = 0.0

    for line in lines:
        text = line.strip()
        if not text:
            continue

        output = aivm.synthesize(
            SynthesisParams(
                text=text,
                voice_id=source_voice_id,
                style_id=source_style_id,
                # 参照に必要なのは声が鳴っている区間だけ。前後の無音は
                # そのぶん latent を食うので付けない。
                pre_silence=0.0,
                post_silence=0.0,
            )
        )
        seconds = output.samples.size / float(output.sample_rate)
        if seconds <= 0.0:
            continue

        clips.append(
            (
                audio_utils.encode_wav(output.samples, sample_rate=output.sample_rate),
                seconds,
            )
        )
        total_seconds += seconds
        if total_seconds >= MAX_REFERENCE_SECONDS:
            break

    if not clips:
        raise BackendError("参照音声を 1 本も合成できませんでした。参照文を確認してください。")
    return clips


def clone_from_aivm(
    *,
    aivm: Sbv2Backend,
    store: VoicePresetStore,
    source_voice_id: str,
    source_style_id: str | None = None,
    name: str,
    description: str = "",
    color_key: str = "shu",
    reference_lines: tuple[str, ...] | None = None,
    with_emotion_styles: bool = True,
    normal_caption: str | None = None,
) -> VoicePreset:
    """取り込んだ話者の声を写した Irodori-TTS 話者を作る。

    ``with_emotion_styles`` を落とすとノーマルだけの話者になる。喜怒哀楽が
    要らない用途では、スタイルの選択肢が減るぶん扱いやすい。

    ``normal_caption`` はノーマルのスタイルにだけ入る。喜怒哀楽のスタイルは
    それぞれ固有の指示を持っているため、混ぜると意図が濁る。
    """

    lines = tuple(reference_lines) if reference_lines else REFERENCE_LINES
    clips = _synthesize_clips(
        aivm,
        source_voice_id=source_voice_id,
        source_style_id=source_style_id,
        lines=lines,
    )
    reference_files = save_reference_wavs([wav for wav, _ in clips])

    styles = build_expression_styles(
        VoiceStyleDef(
            style_id="normal",
            name="ノーマル",
            cfg_scale_speaker=REFERENCE_SPEAKER_CFG,
            cfg_scale_caption=REFERENCE_CAPTION_CFG,
            num_steps=REFERENCE_NUM_STEPS,
        ),
        normal_caption=normal_caption,
        with_emotion=with_emotion_styles,
    )

    return store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=styles,
        reference_files=reference_files,
    )
