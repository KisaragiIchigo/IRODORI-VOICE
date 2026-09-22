"""ユーザー辞書の読み書き。

本家と同じ形の口に加えて、AivisSpeech と同じ形のファイルも受け渡せる。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ...voicevox.aivis_dict import from_aivis_words, to_aivis_words
from ...voicevox.user_dict import DEFAULT_PRIORITY
from .shared import invalidate_audio_cache as _invalidate_audio_cache
from .shared import user_dict_store

router = APIRouter(tags=["voicevox-compat"])


# ---------------------------------------------------------------- ユーザー辞書

@router.get("/user_dict")
def get_user_dict() -> dict[str, dict]:
    return {word_uuid: word.to_json() for word_uuid, word in user_dict_store.list().items()}


@router.post("/user_dict_word", response_model=str)
def add_user_dict_word(
    request: Request,
    surface: str = Query(..., min_length=1, max_length=80),
    pronunciation: str = Query(..., min_length=1, max_length=80),
    accent_type: int = Query(..., ge=0),
    word_type: str | None = Query(None),
    priority: int | None = Query(None, ge=0, le=10),
) -> str:
    try:
        res = user_dict_store.add(
            surface=surface,
            pronunciation=pronunciation,
            accent_type=accent_type,
            word_type=word_type or "PROPER_NOUN",  # type: ignore[arg-type]
            priority=priority if priority is not None else DEFAULT_PRIORITY,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _invalidate_audio_cache(request)
    return res


@router.put("/user_dict_word/{word_uuid}", status_code=204)
def rewrite_user_dict_word(
    request: Request,
    word_uuid: str,
    surface: str = Query(..., min_length=1, max_length=80),
    pronunciation: str = Query(..., min_length=1, max_length=80),
    accent_type: int = Query(..., ge=0),
    word_type: str | None = Query(None),
    priority: int | None = Query(None, ge=0, le=10),
) -> None:
    try:
        user_dict_store.rewrite(
            word_uuid,
            surface=surface,
            pronunciation=pronunciation,
            accent_type=accent_type,
            word_type=word_type,  # type: ignore[arg-type]
            priority=priority,
        )
        _invalidate_audio_cache(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/user_dict_word/{word_uuid}", status_code=204)
def delete_user_dict_word(request: Request, word_uuid: str) -> None:
    try:
        user_dict_store.delete(word_uuid)
        _invalidate_audio_cache(request)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import_user_dict", status_code=204)
def import_user_dict(
    request: Request,
    payload: dict[str, dict] = Body(...),
    override: bool = Query(False),
) -> None:
    user_dict_store.import_words(payload, override=override)
    _invalidate_audio_cache(request)


@router.get("/user_dict/aivis")
def export_user_dict_aivis() -> dict[str, dict]:
    """ユーザー辞書を AivisSpeech の辞書ファイルと同じ形で返す。

    同じ語を AivisSpeech でも使えるようにするための口。互換 API の ``/user_dict`` とは
    キーの書き方と、いくつかの欄が配列かどうかが違う。
    """

    return to_aivis_words(user_dict_store.list())


@router.post("/user_dict/aivis")
def import_user_dict_aivis(
    request: Request,
    payload: Any = Body(...),
    override: bool = Query(True),
) -> dict:
    """AivisSpeech の辞書ファイルを取り込む。

    受け取れなかった語は理由を添えて返し、残りは取り込む。1 語の不備でファイルごと
    突き返すと、何十語もある辞書のどこが悪いのか辿れない。
    """

    try:
        result = from_aivis_words(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result.words:
        user_dict_store.import_words(
            {word_uuid: word.to_json() for word_uuid, word in result.words.items()},
            override=override,
        )
        _invalidate_audio_cache(request)
    return {
        "imported": len(result.words),
        "skipped": result.skipped,
        "total": len(user_dict_store.list()),
        "error": user_dict_store.last_error,
    }
