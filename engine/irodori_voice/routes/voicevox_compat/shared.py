"""互換層のどのエンドポイントからも使う土台。

エンジンの名乗り、話者 ID の対応付け、元テキストの記憶をここへ集める。"""

from __future__ import annotations

from fastapi import HTTPException, Request

from ...voicevox.query_memory import QueryTextMemory
from ...voicevox.speaker_map import SpeakerMap
from ...voicevox.user_dict import shared_user_dict
from ...state import EngineState

# エンジンの識別子。エディタはこの値でエンジンを区別するため、変更してはならない。
ENGINE_UUID = "0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40"

# 本家が名乗るバージョン。外部ツールが下限を見て機能を出し分けることがある。
COMPAT_ENGINE_VERSION = "0.24.1"

query_memory = QueryTextMemory()

user_dict_store = shared_user_dict()


def engine_state(request: Request) -> EngineState:
    return request.app.state.engine


def invalidate_audio_cache(request: Request) -> None:
    """辞書を書き換えたら、古い読みで作った音声を捨てる。

    合成キャッシュの鍵は辞書を当てる前の生の本文なので、辞書だけを変えても鍵が
    変わらない。捨てないと、登録したのに前の読みがそのまま再生される。

    キャッシュを持つのは合成サービスで、バックエンドの一覧を持つ registry ではない。
    起動しきる前はまだ組み立てられていないため、居なければ何もしない。
    """

    service = engine_state(request).service
    if service is not None:
        service.clear_cache()


def speaker_map_for(request: Request) -> SpeakerMap:
    state = engine_state(request)
    if state.registry is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    return SpeakerMap(state.registry.list_voices())
