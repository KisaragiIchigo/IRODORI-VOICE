"""音声合成。"""

from __future__ import annotations

import base64
import io
import json

import soundfile as sf
from fastapi import APIRouter, HTTPException, Request, Response

from .. import audio as audio_utils
from ..backends.base import BackendError, SynthesisParams
from ..schemas import (
    PrefetchOut,
    PrefetchRequest,
    SynthesisBatchRequest,
    SynthesisRequest,
)
from ..synthesis.pipeline import (
    LowBandPolicy,
    OutputFormat,
    SplitPolicy,
    synthesize_pipeline,
)
from ..state import EngineState

router = APIRouter(tags=["synthesis"])


def _state(request: Request) -> EngineState:
    return request.app.state.engine


def _to_params(payload: SynthesisRequest) -> SynthesisParams:
    return SynthesisParams(
        text=payload.text,
        voice_id=payload.voice_id,
        style_id=payload.style_id,
        speed=payload.speed,
        volume=payload.volume,
        pitch=payload.pitch,
        intonation=payload.intonation,
        pre_silence=payload.pre_silence,
        post_silence=payload.post_silence,
        caption=payload.caption,
        style_strength=payload.style_strength,
        seed=payload.seed,
        steps=payload.steps,
    )


@router.post("/synthesis")
def synthesize(request: Request, payload: SynthesisRequest) -> Response:
    """1 行を合成して wav を返す。

    合成の内訳（読み込み・サンプリング・デコードの所要時間、使用シード、キャッシュ命中）は
    ``X-Irodori-Meta`` ヘッダに JSON を base64 で載せる。body は wav そのものに保ち、
    エディタが `<audio>` へ直接流し込めるようにするため。
    """

    state = _state(request)
    if state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    settings = state.settings
    try:
        result = synthesize_pipeline(
            _to_params(payload),
            synthesize_segment=state.service.synthesize,
            split=SplitPolicy(
                enabled=settings.split_long_text,
                target_chars=settings.split_target_chars,
                max_chars=settings.split_max_chars,
                at_quotes=settings.split_at_quotes,
            ),
            output=OutputFormat(),
            low_band=LowBandPolicy(enabled=settings.restore_low_band),
        )
    except BackendError as exc:
        raise HTTPException(status_code=503 if not exc.recoverable else 400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    wav = result.audio.wav
    meta = {
        "used_seed": result.used_seed,
        "sample_rate": result.audio.sample_rate,
        "duration_seconds": round(result.audio.duration_seconds, 3),
        "cached": result.cached,
        "segment_count": result.segment_count,
        "timings": [{"stage": stage, "seconds": round(seconds, 4)} for stage, seconds in result.stage_timings],
        "notes": result.notes,
    }
    encoded_meta = base64.b64encode(json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode("ascii")

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={
            "X-Irodori-Meta": encoded_meta,
            "Cache-Control": "no-store",
        },
    )


@router.post("/synthesis/batch")
def synthesize_batch(request: Request, payload: SynthesisBatchRequest) -> Response:
    """複数行をまとめて 1 本の wav に連結する。書き出し用。"""

    state = _state(request)
    if state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    settings = state.settings
    split = SplitPolicy(
        enabled=settings.split_long_text,
        target_chars=settings.split_target_chars,
        max_chars=settings.split_max_chars,
        at_quotes=settings.split_at_quotes,
    )

    segments = []
    sample_rate: int | None = None
    for index, line in enumerate(payload.lines):
        try:
            result = synthesize_pipeline(
                _to_params(line),
                synthesize_segment=state.service.synthesize,
                split=split,
                output=OutputFormat(),
                low_band=LowBandPolicy(enabled=settings.restore_low_band),
            )
        except BackendError as exc:
            raise HTTPException(status_code=400, detail=f"{index + 1} 行目で失敗しました: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{index + 1} 行目で失敗しました: {exc}") from exc

        decoded, rate = sf.read(io.BytesIO(result.audio.wav), dtype="float32")
        if sample_rate is None:
            sample_rate = int(rate)
        samples = decoded
        if int(rate) != sample_rate:
            samples = audio_utils.resample(
                samples, source_rate=int(rate), target_rate=sample_rate
            )
        if payload.join_silence > 0 and index < len(payload.lines) - 1:
            samples = audio_utils.pad_silence(
                samples,
                sample_rate=sample_rate,
                pre_seconds=0.0,
                post_seconds=payload.join_silence,
            )
        segments.append(samples)

    merged = audio_utils.concat_segments(segments)
    wav = audio_utils.encode_wav(merged, sample_rate=sample_rate or 48000)
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/prefetch", response_model=PrefetchOut)
def prefetch(request: Request, payload: PrefetchRequest) -> PrefetchOut:
    """次に再生されそうな行を裏で作っておく。"""

    state = _state(request)
    if state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    params = _to_params(payload.line)
    already = state.service.is_cached(params)
    queued = False if already else state.service.request_prefetch(params)
    return PrefetchOut(queued=queued, already_cached=already)


@router.delete("/cache")
def clear_cache(request: Request) -> dict[str, bool]:
    state = _state(request)
    if state.service is not None:
        state.service.clear_cache()
    return {"cleared": True}
