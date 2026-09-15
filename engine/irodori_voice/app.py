"""FastAPI アプリの組み立て。

ここは各部品を宣言順に繋ぐだけに専念する。合成もモデル管理もこの層には置かない。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .paths import admin_dist_dir
from .routes import build, library, models, synthesis, system, text, voicevox_compat, voices
from .state import EngineState

# エディタは同一マシンの別プロセスから叩く。開発サーバー、Electron、Tauri の
# それぞれが名乗るオリジンだけを許可する。
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "app://localhost",
    "tauri://localhost",
    "http://tauri.localhost",
    "null",
]

# エディタ向け API のプレフィックス。
API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = EngineState()
    state.bootstrap()
    app.state.engine = state
    state.start_background_load()
    try:
        yield
    finally:
        state.shutdown()


class _RevalidatingStaticFiles(StaticFiles):
    """毎回問い合わせさせる配信。

    Cache-Control を返さないと、ブラウザは Last-Modified からの経過時間で有効期限を
    勝手に決める。管理画面はエンジンを更新するたびに中身が変わるため、古い画面を
    掴んだままになることがある（エディタの中の iframe で起きやすい）。
    ETag と Last-Modified による検証は残るので、変わっていなければ 304 で済む。
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


def create_app(*, editor_dist: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="IRODORI-VOICE Engine",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Irodori-Meta"],
    )

    # エディタ向けの API は /api 配下に置く。VOICEVOX 互換のエンドポイントは
    # パスが仕様で固定されている（/audio_query, /synthesis, /speakers ...）ため、
    # ルート直下はそちらへ明け渡す。
    app.include_router(system.router, prefix=API_PREFIX)
    app.include_router(voices.router, prefix=API_PREFIX)
    app.include_router(synthesis.router, prefix=API_PREFIX)
    app.include_router(library.router, prefix=API_PREFIX)
    app.include_router(models.router, prefix=API_PREFIX)
    app.include_router(build.router, prefix=API_PREFIX)
    app.include_router(text.router, prefix=API_PREFIX)

    # 外部ツール（ゆっくりMovieMaker、AviUtl プラグイン等）からの接続口。
    app.include_router(voicevox_compat.router)

    # 音声モデルと話者を管理する画面。VOICEVOX エディタには無い領域なので、
    # 読み上げの操作とは切り離してここで配信する。ビルドしていなければ出さない。
    admin_dist = admin_dist_dir()
    if admin_dist is not None:
        app.mount("/admin", _RevalidatingStaticFiles(directory=str(admin_dist), html=True), name="admin")

    # ビルド済みエディタが隣にあれば同一オリジンで配信する。ブラウザだけで使いたい場合や、
    # デスクトップシェルを介さずに動作確認したい場合の経路。
    if editor_dist is not None and editor_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(editor_dist), html=True), name="editor")

    return app
