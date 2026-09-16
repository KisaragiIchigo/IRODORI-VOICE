"""このエンジンが応えない機能。

本家にある口だけは開けておく。外部ツールは存在しないエンドポイントを
異常として扱うことがあり、404 を返すと合成まで進まなくなる。"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Response

from ...voicevox.schemas import Speaker

router = APIRouter(tags=["voicevox-compat"])


# ------------------------------------------------------- 非対応として明示する機能

@router.get("/singers", response_model=list[Speaker])
def singers() -> list[Speaker]:
    """歌唱用の話者。このエンジンは歌唱合成に対応しないため常に空。"""

    return []


@router.get("/singer_info")
def singer_info() -> dict:
    raise HTTPException(status_code=404, detail="このエンジンは歌唱合成に対応していません。")


@router.post("/morphable_targets", response_model=list[dict])
def morphable_targets(base_speakers: list[int] = Body(...)) -> list[dict]:
    """モーフィング可能な組み合わせ。対応しないため、すべて不可として返す。"""

    return [{} for _ in base_speakers]


@router.post("/synthesis_morphing")
def synthesis_morphing() -> Response:
    raise HTTPException(
        status_code=400,
        detail="このエンジンはモーフィング合成に対応していません。",
    )


@router.post("/validate_kana", response_model=bool)
def validate_kana(text: str = Query(...)) -> bool:
    """AquesTalk 風記法の検証。この記法には対応しないため常に不可として返す。"""

    raise HTTPException(
        status_code=400,
        detail="このエンジンは AquesTalk 風記法に対応していません。",
    )
