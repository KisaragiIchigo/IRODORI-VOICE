"""AudioQuery から wav を作る経路。

合成の手順そのものは synthesis/pipeline.py が持つ。ここは受け取った値を
パイプラインの言葉へ翻訳し、結果を HTTP の応答へ載せることに専念する。"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Body, HTTPException, Query, Request, Response

from ... import audio as audio_utils
from ...backends.base import BackendError, SynthesisParams
from ...voicevox.schemas import DEFAULT_OUTPUT_SAMPLING_RATE, AudioQuery
from ...synthesis.pipeline import (
    LowBandPolicy,
    OutputFormat,
    PipelineResult,
    SplitPolicy,
    apply_output_format,
    synthesize_pipeline,
)
from ...state import EngineState
from .shared import engine_state, speaker_map_for
from .text_resolution import resolve_source_text

router = APIRouter(tags=["voicevox-compat"])


# 読み上げる音が無いときの最短の長さ。前後の無音をどちらも 0 にされた場合、
# 0 フレームの wav は Web Audio の decodeAudioData が読めず、受け取った側で
# 別のエラーになる。耳に付かない範囲の長さを必ず持たせる。
MIN_SILENCE_SECONDS = 0.01


def _silence_response(payload: AudioQuery) -> Response:
    """前後の無音だけの wav を返す。

    「＊＊＊＊＊」「……」のような記号だけの行は OpenJTalk が音素を作れず、
    アクセント句が 0 件になる。本家 VOICEVOX はこの場合も前後の無音ぶんの wav を
    返すため、同じ形に合わせる。エラーにすると、連続再生やまとめ書き出しが
    その行で止まってしまう。

    無音の長さに speedScale は掛けない。このエンジンは前後の無音を合成後の波形へ
    足す作りで、読み上げ部分の速度とは独立しているため。
    """

    pre = max(0.0, min(audio_utils.MAX_SILENCE_SECONDS, float(payload.prePhonemeLength)))
    post = max(0.0, min(audio_utils.MAX_SILENCE_SECONDS, float(payload.postPhonemeLength)))
    sample_rate = int(payload.outputSamplingRate) or DEFAULT_OUTPUT_SAMPLING_RATE

    seconds = max(MIN_SILENCE_SECONDS, pre + post)
    samples = np.zeros(int(seconds * sample_rate), dtype=np.float32)

    formatted = apply_output_format(
        samples,
        source_rate=sample_rate,
        output=OutputFormat(sample_rate=sample_rate, stereo=bool(payload.outputStereo)),
    )
    return Response(
        content=formatted.wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


# モデルへの指示速度は、声質が最も安定する 1.0 倍へ固定する。速度の指定は
# 合成し終えた波形を伸縮して当てる。早口を直接指示すると生成そのものが崩れる。
MODEL_SPEED = 1.0


def _synthesis_params(
    payload: AudioQuery, *, text: str, voice_id: str, style_id: str
) -> SynthesisParams:
    """AudioQuery を、バックエンドが受け取る形へ翻訳する。

    受け取った値はモデルが壊れない範囲へ丸めてから渡す。エディタは範囲外の値も
    送れるため、ここが境界になる。
    """

    return SynthesisParams(
        text=text,
        voice_id=voice_id,
        style_id=style_id,
        speed=MODEL_SPEED,
        volume=max(0.0, min(2.0, float(payload.volumeScale))),
        pitch=max(-0.15, min(0.15, float(payload.pitchScale))),
        intonation=max(0.0, min(2.0, float(payload.intonationScale))),
        pre_silence=max(0.0, min(10.0, float(payload.prePhonemeLength))),
        post_silence=max(0.0, min(10.0, float(payload.postPhonemeLength))),
        seed=None,
    )


def _run_pipeline(
    state: EngineState, params: SynthesisParams, output: OutputFormat, *, speed_scale: float
) -> PipelineResult:
    """パイプラインを設定どおりに回し、失敗を HTTP の応答へ翻訳する。"""

    settings = state.settings
    try:
        return synthesize_pipeline(
            params,
            synthesize_segment=state.service.synthesize,
            split=SplitPolicy(
                enabled=settings.split_long_text,
                target_chars=settings.split_target_chars,
                max_chars=settings.split_max_chars,
                at_quotes=settings.split_at_quotes,
            ),
            output=output,
            low_band=LowBandPolicy(enabled=settings.restore_low_band),
            speed_scale=speed_scale,
        )
    except BackendError as exc:
        raise HTTPException(
            status_code=503 if not exc.recoverable else 400,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/synthesis")
def synthesis(
    request: Request,
    payload: AudioQuery,
    speaker: int = Query(...),
    enable_interrogative_upspeak: bool = Query(True),
) -> Response:
    """AudioQuery から wav を合成する。

    話者を解き、テキストを取り戻し、話速と出力形式をパイプラインへ渡す。
    """

    state = engine_state(request)
    if state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    try:
        voice_id, style_id = speaker_map_for(request).resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = resolve_source_text(payload)
    if text.strip() == "":
        return _silence_response(payload)

    result = _run_pipeline(
        state,
        _synthesis_params(payload, text=text, voice_id=voice_id, style_id=style_id),
        OutputFormat(
            sample_rate=int(payload.outputSamplingRate) or None,
            stereo=bool(payload.outputStereo),
        ),
        speed_scale=float(payload.speedScale),
    )

    return Response(
        content=result.audio.wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )

@router.post("/connect_waves")
def connect_waves(waves: list[str] = Body(...)) -> Response:
    """base64 の wav を順に連結して 1 本にする。

    エディタが「文章をまとめて書き出し」で使う。レートが混在する場合は
    最初の 1 本に合わせる。
    """

    import base64

    if not waves:
        raise HTTPException(status_code=422, detail="結合する音声がありません。")

    segments: list[np.ndarray] = []
    sample_rate: int | None = None
    for encoded in waves:
        try:
            data, rate = sf.read(io.BytesIO(base64.b64decode(encoded)), dtype="float32", always_2d=True)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"音声を読み取れませんでした: {exc}") from exc

        if data.shape[1] not in (1, 2):
            raise HTTPException(status_code=422, detail="結合できる音声はモノラルまたはステレオです。")
        data = audio_utils.as_stereo(data)
        if sample_rate is None:
            sample_rate = int(rate)
        elif int(rate) != sample_rate:
            data = audio_utils.resample(data, source_rate=int(rate), target_rate=sample_rate)
        segments.append(data.astype(np.float32, copy=False))

    merged = audio_utils.concat_segments(segments)
    wav = audio_utils.encode_wav(merged, sample_rate=sample_rate or 24000)
    return Response(content=wav, media_type="audio/wav")


@router.post("/multi_synthesis")
def multi_synthesis(
    request: Request,
    payload: list[AudioQuery],
    speaker: int = Query(...),
) -> Response:
    """複数の AudioQuery をまとめて合成し、zip で返す。"""

    import zipfile

    if not payload:
        raise HTTPException(status_code=422, detail="合成する要求がありません。")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, query in enumerate(payload):
            wav_response = synthesis(request, query, speaker=speaker)
            archive.writestr(f"{index + 1:03d}.wav", wav_response.body)
    return Response(content=buffer.getvalue(), media_type="application/zip")
