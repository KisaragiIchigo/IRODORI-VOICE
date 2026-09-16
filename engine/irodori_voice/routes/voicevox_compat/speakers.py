"""話者の一覧・詳細・読み込みの準備。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ...voicevox.manifest_docs import speaker_policy
from ...voicevox.portrait import icon_for, portrait_for
from ...voicevox.speaker_image import icon_base64, portrait_base64
from ...voicevox.sample_voice import sample_store
from ...voicevox.schemas import Speaker
from ...voicevox.speaker_map import speaker_uuid_for
from .shared import engine_state, speaker_map_for

router = APIRouter(tags=["voicevox-compat"])


@router.get("/speakers", response_model=list[Speaker])
def speakers(request: Request) -> list[Speaker]:
    return speaker_map_for(request).speakers


@router.get("/speaker_info")
def speaker_info(request: Request, speaker_uuid: str = Query(...)) -> dict:
    """話者の詳細。

    icon と portrait は base64 の画像として扱われるため、空文字列を返してはならない
    （エディタが画像形式を判定できず例外になる）。利用者がアイコンを付けていれば
    その画像を、付けていなければ話者が持つ画像か識別色から描いた図形を返す。

    スタイルごとの立ち絵（style_infos[].portrait）は載せない。値は話者で共通なのに
    スタイルの数だけ base64 が直列化され、一覧を開くたびの転送量が膨らむ。
    エディタはこの項目が無ければ話者の立ち絵へ落ちる。
    """

    state = engine_state(request)
    mapping = speaker_map_for(request)
    speaker = mapping.find_by_uuid(speaker_uuid)
    if speaker is None:
        raise HTTPException(status_code=404, detail="指定された話者が見つかりません。")

    voice = None
    if state.registry is not None:
        for candidate in state.registry.list_voices():
            if speaker_uuid_for(candidate.voice_id) == speaker_uuid:
                voice = candidate
                break

    icon = icon_base64(voice) if voice is not None else icon_for("shu")
    portrait = portrait_base64(voice) if voice is not None else portrait_for("shu")

    style_infos = []
    for style in speaker.styles:
        internal = mapping.resolve(style.id)
        style_infos.append(
            {
                "id": style.id,
                "icon": icon,
                # 作り置きがあれば実際の音声を、無ければ無音を返して裏で生成する。
                # 空配列にすると、エディタが undefined を audio.src へ代入して落ちる。
                "voice_samples": sample_store.samples_for(internal[0], internal[1]),
            }
        )

    return {
        "policy": speaker_policy(
            voice.backend_id if voice is not None else None,
            voice.voice_id if voice is not None else None,
            voice.has_reference if voice is not None else False,
        ),
        "portrait": portrait,
        "style_infos": style_infos,
    }


# ---------------------------------------------------------------- 話者の準備

@router.post("/initialize_speaker", status_code=204)
def initialize_speaker(
    request: Request,
    speaker: int = Query(...),
    skip_reinit: bool = Query(False),
) -> None:
    """話者を使える状態にする。

    本家では話者ごとにモデルを読み込むが、こちらは 1 つのモデルで全話者を賄うため、
    存在確認だけを行う。モデル本体の読み込みはエンジン起動時に済んでいる。
    """

    try:
        speaker_map_for(request).resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/is_initialized_speaker", response_model=bool)
def is_initialized_speaker(request: Request, speaker: int = Query(...)) -> bool:
    try:
        speaker_map_for(request).resolve(speaker)
    except KeyError:
        return False
    state = engine_state(request)
    return state.status != "error"
