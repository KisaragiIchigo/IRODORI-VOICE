"""話者を残さずに、シード値の声だけを試す。"""

from __future__ import annotations

import base64
import json
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from ... import audio as audio_utils
from ...analysis import estimate_pitch
from ...backends.base import BackendError, SynthesisParams
from ...backends.irodori.backend import voice_id_for
from ...schemas import SeedPreviewRequest
from ...voices.store import VoiceStyleDef
from .shared import engine_state

router = APIRouter(tags=["voices"])


@router.post("/voices/preview-seed")
def preview_seed(request: Request, payload: SeedPreviewRequest) -> Response:
    """話者を作らずに、シード値の声を試す。

    合成には話者の定義が要るため、一時の話者を作って使い、終わったら必ず消す。
    保存されるものは何も残らない。

    本文は wav、声の高さの測定結果は ``X-Irodori-Preview`` ヘッダへ base64 で載せる。
    """

    state = engine_state(request)
    if state.store is None or state.irodori is None or state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    preset = state.store.create(
        name=f"__preview_{uuid.uuid4().hex[:8]}",
        description="試聴のための一時的な話者",
        color_key="shu",
        mode="caption",
        styles=[
            VoiceStyleDef(
                style_id="normal",
                name="ノーマル",
                caption=(payload.caption or "").strip() or None,
            )
        ],
        voice_seed=payload.seed,
    )

    try:
        # service.synthesize は (結果, キャッシュヒットか) を返す。
        result, _cached = state.service.synthesize(
            SynthesisParams(
                text=payload.text,
                voice_id=voice_id_for(preset),
                style_id="normal",
            )
        )
    except BackendError as exc:
        raise HTTPException(status_code=503 if not exc.recoverable else 400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # 合成が失敗しても一時の話者は残さない。
        state.store.delete(preset.preset_id)

    wav = audio_utils.encode_wav_stereo(result.samples, sample_rate=result.sample_rate)

    pitch = estimate_pitch(result.samples, result.sample_rate)
    meta = {
        "seed": payload.seed,
        "used_seed": result.used_seed,
        "sample_rate": result.sample_rate,
        "duration_seconds": round(len(result.samples) / result.sample_rate, 3),
        "pitch": pitch.to_dict() if pitch is not None else None,
    }
    encoded = base64.b64encode(json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode("ascii")

    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"X-Irodori-Preview": encoded, "Cache-Control": "no-store"},
    )
