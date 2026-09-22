"""フレーズ分割辞書の読み書き。

辞書そのものの扱いは voicevox/word_splits.py が持つ。ここは HTTP の口だけ。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...voicevox.word_splits import load_splits, save_splits
from .shared import invalidate_audio_cache

router = APIRouter(tags=["voicevox-compat"])


@router.get("/word_splits")
def get_word_splits() -> dict[str, str]:
    """フレーズ分割辞書の中身を返す。"""

    return load_splits()


@router.post("/word_splits")
def update_word_splits(request: Request, splits: dict[str, str]) -> dict:
    """フレーズ分割辞書を書き換える。

    合成キャッシュの鍵は分割を当てる前の生の本文なので、区切りを変えても鍵が変わらない。
    捨てないと、登録したのに前の区切りで作った音がそのまま再生される。
    """

    save_splits(splits)
    invalidate_audio_cache(request)
    return {"status": "ok"}
