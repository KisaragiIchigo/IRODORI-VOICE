"""テキストからアクセント句を組み立てる経路。"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query, Request

from ...voicevox.schemas import DEFAULT_OUTPUT_SAMPLING_RATE, AccentPhrase, AudioQuery
from ...voicevox.user_dict import count_moras
from ...voicevox.word_splits import apply_word_splits
from .shared import query_memory, speaker_map_for
from .text_resolution import accent_phrases_for

router = APIRouter(tags=["voicevox-compat"])


@router.post("/audio_query", response_model=AudioQuery)
def audio_query(
    request: Request,
    text: str = Query(..., max_length=2000),
    speaker: int = Query(...),
) -> AudioQuery:
    """テキストから音声クエリを構築する。

    本家と同じく OpenJTalk でアクセント句を構築し、テキストと一緒に ``/synthesis`` へ
    引き継げるよう辞書へキャッシュする（AudioQuery には表記が含まれないため）。
    """
    
    text = apply_word_splits(text)

    mapping = speaker_map_for(request)
    try:
        mapping.resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    phrases = accent_phrases_for(text)

    if phrases:
        query_memory.remember(phrases, text)

    return AudioQuery(
        accent_phrases=phrases,
        speedScale=1.0,
        pitchScale=0.0,
        intonationScale=1.0,
        volumeScale=1.0,
        prePhonemeLength=0.1,
        postPhonemeLength=0.1,
        outputSamplingRate=DEFAULT_OUTPUT_SAMPLING_RATE,
        # 元の表記を添えて返す。VOICEVOX の AudioQuery は読みしか持たないため、
        # これが無いと /synthesis 側で漢字混じりの表記を取り戻せない。エディタは
        # この値をプロジェクトへ保存して送り返すので、エンジンを再起動しても残る。
        kana=text,
    )


@router.post("/accent_phrases", response_model=list[AccentPhrase])
def accent_phrases(
    request: Request,
    text: str = Query(..., max_length=2000),
    speaker: int = Query(...),
    is_kana: bool = Query(False),
) -> list[AccentPhrase]:
    
    text = apply_word_splits(text)
    
    mapping = speaker_map_for(request)
    try:
        mapping.resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    processed_text = text.replace("'", "") if is_kana else text
    phrases = accent_phrases_for(processed_text)

    if is_kana and len(phrases) > 1:
        # 辞書画面はカタカナに「ガ'」のようなアクセント記号を添えて送ってくる。
        # 1 語として登録するものなので、句が割れても 1 つへまとめ直して返す。
        combined_moras = []
        for phrase in phrases:
            combined_moras.extend(phrase.moras)

        # アクセント位置は「'」の前にあるカタカナのモーラ数。記号が無ければ 0（平板）。
        accent = 0
        matched = re.search(r"^([ァ-ヴー]+)'", text)
        if matched is not None:
            accent = count_moras(matched.group(1))

        phrases = [
            AccentPhrase(
                moras=combined_moras,
                accent=accent,
                pause_mora=None,
                is_interrogative=False,
            )
        ]

    if phrases:
        query_memory.remember(phrases, text)
    return phrases


@router.post("/mora_data", response_model=list[AccentPhrase])
def mora_data(
    request: Request,
    payload: list[AccentPhrase],
    speaker: int = Query(...),
) -> list[AccentPhrase]:
    """モーラの長さと音高を埋めて返す。

    Irodori-TTS はモーラ単位の予測値を持たないため、受け取った内容をそのまま返す。
    外部ツールはこの往復が成立していれば動作する。
    """

    speaker_map_for(request)
    return payload
