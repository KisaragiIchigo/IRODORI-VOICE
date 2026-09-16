"""フレーズ分割辞書の読み書き。

辞書そのものの扱いは voicevox/word_splits.py が持つ。ここは HTTP の口だけ。"""

from __future__ import annotations

from fastapi import APIRouter

from ...voicevox.word_splits import load_splits, save_splits

router = APIRouter(tags=["voicevox-compat"])


@router.get("/word_splits")
def get_word_splits() -> dict[str, str]:
    """フレーズ分割辞書の中身を返す。"""

    return load_splits()


@router.post("/word_splits")
def update_word_splits(splits: dict[str, str]) -> dict:
    """フレーズ分割辞書を書き換える。"""

    save_splits(splits)
    return {"status": "ok"}
