"""話者の一覧と、利用者が作るプリセットの管理。"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    creation,
    crud,
    icon,
    preview,
    reference,
)

router = APIRouter(tags=["voices"])

# 登録順がそのまま照合順になる。voice_id は「/」を含みうる path 変数なので、
# DELETE /voices/{voice_id} を先に置くと /voices/{voice_id}/icon まで飲み込む。
# 細かいパスを持つものから並べること。
router.include_router(icon.router)
router.include_router(reference.router)
router.include_router(creation.router)
router.include_router(preview.router)
router.include_router(crud.router)

__all__ = ["router"]
