"""VOICEVOX ENGINE 互換 API。

ゆっくりMovieMaker や AviUtl プラグインなど、VOICEVOX 対応を謳う外部ツールから
そのまま叩けるようにするための層。エンドポイントの形とフィールド名を本家に合わせる。

対応の程度を正直に書いておく。

  - ``/audio_query`` は OpenJTalk でアクセント句を組み立てて返す。本家と同じ手順。
  - アクセントやモーラ長を編集しても Irodori-TTS の音には反映されない。
    このモデルはテキストから直接 latent を生成し、モーラ単位の制御機構を持たない。
    Style-Bert-VITS2 も同様にモーラ長の直接指定は受けない。
  - speedScale / volumeScale / prePhonemeLength / postPhonemeLength は反映される。
    pitchScale と intonationScale は、対応する話者でのみ効く。

つまり「読み上げさせる」用途では本家と同じように使え、「アクセントを細かく直す」
用途には応えられない。外部ツールの多くは前者しか使わないため、実用上は繋がる。
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Body, HTTPException, Query, Request, Response

from .. import audio as audio_utils
from ..backends.base import BackendError, SynthesisParams
from ..voicevox.accent import accent_phrases_to_text, build_accent_phrases, pyopenjtalk_available
from ..voicevox.icon import ENGINE_ICON_BASE64
from ..voicevox.manifest_docs import (
    DEPENDENCY_LICENSES,
    ENGINE_TERMS_OF_SERVICE,
    ENGINE_UPDATE_INFOS,
    speaker_policy,
)
from ..voicevox.portrait import icon_for, portrait_for
from ..voicevox.speaker_image import icon_base64, portrait_base64
from ..voicevox.sample_voice import sample_store
from ..voicevox.query_memory import QueryTextMemory, phrase_key
from ..voicevox.schemas import (
    DEFAULT_OUTPUT_SAMPLING_RATE,
    AccentPhrase,
    AudioQuery,
    Speaker,
    SupportedDevices,
)
from ..synthesis.pipeline import (
    LowBandPolicy,
    OutputFormat,
    SplitPolicy,
    apply_output_format,
    synthesize_pipeline,
)
from ..voicevox.speaker_map import SpeakerMap, speaker_uuid_for
from ..voicevox.aivis_dict import from_aivis_words, to_aivis_words
from ..voicevox.user_dict import (
    DEFAULT_PRIORITY,
    shared_user_dict,
)
from ..state import EngineState

router = APIRouter(tags=["voicevox-compat"])

# エンジンの識別子。エディタはこの値でエンジンを区別するため、変更してはならない。
ENGINE_UUID = "0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40"

_query_memory = QueryTextMemory()
_user_dict = shared_user_dict()

# 本家が名乗るバージョン。外部ツールが下限を見て機能を出し分けることがある。
COMPAT_ENGINE_VERSION = "0.24.1"


def _state(request: Request) -> EngineState:
    return request.app.state.engine


def _speaker_map(request: Request) -> SpeakerMap:
    state = _state(request)
    if state.registry is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")
    return SpeakerMap(state.registry.list_voices())


# 読み上げる音が無いときの最短の長さ。前後の無音をどちらも 0 にされた場合、
# 0 フレームの wav は Web Audio の decodeAudioData が読めず、受け取った側で
# 別のエラーになる。耳に付かない範囲の長さを必ず持たせる。
MIN_SILENCE_SECONDS = 0.01


def _silence_response(payload: AudioQuery) -> Response:
    """前後の無音だけの wav を返す。

    「＊＊＊＊＊」「……」のような記号だけの行は OpenJTalk が音素を作れず、
    アクセント句が 0 件になる。本家 VOICEVOX はこの場合も前後の無音ぶんの wav を
    返すため、同じ形に合わせる。エラーにすると、連続再生やまとめ書き出しが
    その行で止まってしまう。

    無音の長さに speedScale は掛けない。このエンジンは前後の無音を合成後の波形へ
    足す作りで、読み上げ部分の速度とは独立しているため。
    """

    pre = max(0.0, min(audio_utils.MAX_SILENCE_SECONDS, float(payload.prePhonemeLength)))
    post = max(0.0, min(audio_utils.MAX_SILENCE_SECONDS, float(payload.postPhonemeLength)))
    sample_rate = int(payload.outputSamplingRate) or DEFAULT_OUTPUT_SAMPLING_RATE

    seconds = max(MIN_SILENCE_SECONDS, pre + post)
    samples = np.zeros(int(seconds * sample_rate), dtype=np.float32)

    formatted = apply_output_format(
        samples,
        source_rate=sample_rate,
        output=OutputFormat(sample_rate=sample_rate, stereo=bool(payload.outputStereo)),
    )
    return Response(
        content=formatted.wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


def _text_from_kana(payload: AudioQuery) -> str | None:
    """AudioQuery に添えておいた元の表記を、読みが一致するときだけ採り出す。

    利用者がエディタで読みを直した場合、``kana`` は直す前の表記のまま送られて
    くる。読みを組み直して突き合わせ、一致するときだけ採用する。
    """

    kana = (payload.kana or "").strip()
    if kana == "":
        return None

    rebuilt = build_accent_phrases(kana)
    if not rebuilt or phrase_key(rebuilt) != phrase_key(payload.accent_phrases):
        return None
    return kana


def _resolve_source_text(payload: AudioQuery) -> str:
    """合成に使うテキストを決める。

    元の表記が分かればそちらを使う。読みだけで合成すると長音が母音字のまま
    モデルへ渡り（「カード」が「カアド」）、別の語に化ける。

    記憶はプロセス内にしか無く、エンジンの再起動やプロジェクトの開き直しで
    外れる。その穴を ``kana`` に載せた表記が埋める。
    """

    remembered = _query_memory.recall(payload.accent_phrases)
    if remembered is not None:
        return remembered

    from_kana = _text_from_kana(payload)
    if from_kana is not None:
        # 次からは組み直しを省けるよう覚えておく。
        _query_memory.remember(payload.accent_phrases, from_kana)
        return from_kana

    return accent_phrases_to_text(payload.accent_phrases)


@router.get("/version")
def version() -> str:
    return COMPAT_ENGINE_VERSION


@router.get("/engine_manifest")
def engine_manifest(request: Request) -> dict:
    """エンジンの自己申告。

    フィールド名と型は VOICEVOX の openapi 定義に厳密に合わせる。
    ``supported_features`` は boolean の直値でなければならない（構造体を返すと
    エディタ側で truthy と判定され、対応していない機能の UI が出てしまう）。
    """

    state = _state(request)
    return {
        "manifest_version": "0.13.1",
        "name": "IRODORI-VOICE Engine",
        "brand_name": "IRODORI-VOICE",
        "uuid": ENGINE_UUID,
        "url": "https://github.com/Aratako/Irodori-TTS",
        "icon": ENGINE_ICON_BASE64,
        "default_sampling_rate": DEFAULT_OUTPUT_SAMPLING_RATE,
        "frame_rate": 93.75,
        "terms_of_service": ENGINE_TERMS_OF_SERVICE,
        "update_infos": ENGINE_UPDATE_INFOS,
        "dependency_licenses": DEPENDENCY_LICENSES,
        "supported_features": {
            # モーラ単位の制御機構を持たないため、編集系はすべて false。
            # false を返すことでエディタ側が該当コントロールを無効化する。
            "adjust_mora_pitch": False,
            "adjust_phoneme_length": False,
            "adjust_speed_scale": True,
            "adjust_pitch_scale": False,
            "adjust_intonation_scale": False,
            "adjust_volume_scale": True,
            "adjust_pause_length": False,
            "interrogative_upspeak": False,
            "synthesis_morphing": False,
            "sing": False,
            "manage_library": False,
            "return_resource_url": False,
            "apply_katakana_english": False,
        },
        "detail": state.detail,
    }


@router.get("/supported_devices", response_model=SupportedDevices)
def supported_devices(request: Request) -> SupportedDevices:
    state = _state(request)
    placement = state.placement
    return SupportedDevices(
        cpu=True,
        cuda=bool(placement is not None and placement.model_device == "cuda"),
        dml=False,
    )


@router.get("/speakers", response_model=list[Speaker])
def speakers(request: Request) -> list[Speaker]:
    return _speaker_map(request).speakers


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

    state = _state(request)
    mapping = _speaker_map(request)
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


@router.post("/audio_query", response_model=AudioQuery)
def audio_query(
    request: Request,
    text: str = Query(..., max_length=2000),
    speaker: int = Query(...),
) -> AudioQuery:
    """テキストから合成パラメータを組み立てる。

    本家と同じく OpenJTalk でアクセント句を作る。元テキストは ``/synthesis`` で
    使えるよう控えておく（AudioQuery には表記が含まれないため）。
    """

    mapping = _speaker_map(request)
    try:
        mapping.resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    phrases = build_accent_phrases(text)
    if phrases:
        _query_memory.remember(phrases, text)

    return AudioQuery(
        accent_phrases=phrases,
        speedScale=1.0,
        pitchScale=0.0,
        intonationScale=1.0,
        volumeScale=1.0,
        prePhonemeLength=0.1,
        postPhonemeLength=0.1,
        outputSamplingRate=DEFAULT_OUTPUT_SAMPLING_RATE,
        outputStereo=False,
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
    mapping = _speaker_map(request)
    try:
        mapping.resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    phrases = build_accent_phrases(text)
    if phrases:
        _query_memory.remember(phrases, text)
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

    _speaker_map(request)
    return payload


@router.post("/synthesis")
def synthesis(
    request: Request,
    payload: AudioQuery,
    speaker: int = Query(...),
    enable_interrogative_upspeak: bool = Query(True),
) -> Response:
    """AudioQuery から wav を合成する。"""

    state = _state(request)
    if state.service is None:
        raise HTTPException(status_code=503, detail="エンジンが初期化されていません。")

    mapping = _speaker_map(request)
    try:
        voice_id, style_id = mapping.resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = _resolve_source_text(payload)
    if text.strip() == "":
        return _silence_response(payload)

    params = SynthesisParams(
        text=text,
        voice_id=voice_id,
        style_id=style_id,
        speed=max(0.5, min(2.0, float(payload.speedScale))),
        volume=max(0.0, min(2.0, float(payload.volumeScale))),
        pitch=max(-0.15, min(0.15, float(payload.pitchScale))),
        intonation=max(0.0, min(2.0, float(payload.intonationScale))),
        pre_silence=max(0.0, min(10.0, float(payload.prePhonemeLength))),
        post_silence=max(0.0, min(10.0, float(payload.postPhonemeLength))),
        # シードは渡さない。パイプラインが話者から安定した値を導出する。
        # テキストから導出すると行ごとに別人になり、hash() を使うと再起動で声が変わる。
        seed=None,
    )

    settings = state.settings
    try:
        result = synthesize_pipeline(
            params,
            synthesize_segment=state.service.synthesize,
            split=SplitPolicy(
                enabled=settings.split_long_text,
                target_chars=settings.split_target_chars,
                max_chars=settings.split_max_chars,
            ),
            output=OutputFormat(
                sample_rate=int(payload.outputSamplingRate) or None,
                stereo=bool(payload.outputStereo),
            ),
            low_band=LowBandPolicy(enabled=settings.restore_low_band),
        )
    except BackendError as exc:
        # 回復不能な要因（モデル形式が非対応など）は 503、
        # 要求の内容で直せるものは 400 として返す。500 だと
        # エディタ側が理由を出さず「エラーが発生しました」で終わってしまう。
        raise HTTPException(
            status_code=503 if not exc.recoverable else 400,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(
        content=result.audio.wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


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
        _speaker_map(request).resolve(speaker)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/is_initialized_speaker", response_model=bool)
def is_initialized_speaker(request: Request, speaker: int = Query(...)) -> bool:
    try:
        _speaker_map(request).resolve(speaker)
    except KeyError:
        return False
    state = _state(request)
    return state.status != "error"


@router.get("/core_versions", response_model=list[str])
def core_versions() -> list[str]:
    return [COMPAT_ENGINE_VERSION]


# ---------------------------------------------------------------- 音声の加工

@router.post("/connect_waves")
def connect_waves(waves: list[str] = Body(...)) -> Response:
    """base64 の wav を順に連結して 1 本にする。

    エディタが「文章をまとめて書き出し」で使う。レートが混在する場合は
    最初の 1 本に合わせる。
    """

    import base64

    if not waves:
        raise HTTPException(status_code=422, detail="結合する音声がありません。")

    segments: list[np.ndarray] = []
    sample_rate: int | None = None
    for encoded in waves:
        try:
            data, rate = sf.read(io.BytesIO(base64.b64decode(encoded)), dtype="float32")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"音声を読み取れませんでした: {exc}") from exc

        if data.ndim == 2:
            data = data.mean(axis=1)
        if sample_rate is None:
            sample_rate = int(rate)
        elif int(rate) != sample_rate:
            data = audio_utils.resample(data, source_rate=int(rate), target_rate=sample_rate)
        segments.append(data.astype(np.float32, copy=False))

    merged = audio_utils.concat_segments(segments)
    wav = audio_utils.encode_wav(merged, sample_rate=sample_rate or 24000)
    return Response(content=wav, media_type="audio/wav")


@router.post("/multi_synthesis")
def multi_synthesis(
    request: Request,
    payload: list[AudioQuery],
    speaker: int = Query(...),
) -> Response:
    """複数の AudioQuery をまとめて合成し、zip で返す。"""

    import zipfile

    if not payload:
        raise HTTPException(status_code=422, detail="合成する要求がありません。")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, query in enumerate(payload):
            wav_response = synthesis(request, query, speaker=speaker)
            archive.writestr(f"{index + 1:03d}.wav", wav_response.body)
    return Response(content=buffer.getvalue(), media_type="application/zip")


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


# ---------------------------------------------------------------- ユーザー辞書

@router.get("/user_dict")
def get_user_dict() -> dict[str, dict]:
    return {word_uuid: word.to_json() for word_uuid, word in _user_dict.list().items()}


@router.post("/user_dict_word", response_model=str)
def add_user_dict_word(
    surface: str = Query(..., min_length=1, max_length=80),
    pronunciation: str = Query(..., min_length=1, max_length=80),
    accent_type: int = Query(..., ge=0),
    word_type: str | None = Query(None),
    priority: int | None = Query(None, ge=0, le=10),
) -> str:
    return _user_dict.add(
        surface=surface,
        pronunciation=pronunciation,
        accent_type=accent_type,
        word_type=word_type or "PROPER_NOUN",  # type: ignore[arg-type]
        priority=priority if priority is not None else DEFAULT_PRIORITY,
    )


@router.put("/user_dict_word/{word_uuid}", status_code=204)
def rewrite_user_dict_word(
    word_uuid: str,
    surface: str = Query(..., min_length=1, max_length=80),
    pronunciation: str = Query(..., min_length=1, max_length=80),
    accent_type: int = Query(..., ge=0),
    word_type: str | None = Query(None),
    priority: int | None = Query(None, ge=0, le=10),
) -> None:
    try:
        _user_dict.rewrite(
            word_uuid,
            surface=surface,
            pronunciation=pronunciation,
            accent_type=accent_type,
            word_type=word_type,  # type: ignore[arg-type]
            priority=priority,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/user_dict_word/{word_uuid}", status_code=204)
def delete_user_dict_word(word_uuid: str) -> None:
    try:
        _user_dict.delete(word_uuid)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import_user_dict", status_code=204)
def import_user_dict(
    payload: dict[str, dict] = Body(...),
    override: bool = Query(False),
) -> None:
    _user_dict.import_words(payload, override=override)


@router.get("/user_dict/aivis")
def export_user_dict_aivis() -> dict[str, dict]:
    """ユーザー辞書を AivisSpeech の辞書ファイルと同じ形で返す。

    同じ語を AivisSpeech でも使えるようにするための口。互換 API の ``/user_dict`` とは
    キーの書き方と、いくつかの欄が配列かどうかが違う。
    """

    return to_aivis_words(_user_dict.list())


@router.post("/user_dict/aivis")
def import_user_dict_aivis(
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
        _user_dict.import_words(
            {word_uuid: word.to_json() for word_uuid, word in result.words.items()},
            override=override,
        )
    return {
        "imported": len(result.words),
        "skipped": result.skipped,
        "total": len(_user_dict.list()),
        "error": _user_dict.last_error,
    }


@router.get("/update_infos.json")
def update_infos_json() -> list[dict]:
    """更新情報の一覧。

    エディタは起動時にこれを取得する。外部サイトを指すと無関係な更新情報が
    表示されてしまうため、エンジン自身が空の一覧を返してオフラインで完結させる。
    """

    return []


@router.get("/compat_status")
def compat_status() -> dict:
    """互換層がどこまで応えられるかを、利用者に伝えるための情報。"""

    return {
        "engine_version": COMPAT_ENGINE_VERSION,
        "accent_analysis": "pyopenjtalk" if pyopenjtalk_available() else "簡易（カタカナのみ）",
        "user_dict": _user_dict.last_error or f"有効（登録語 {len(_user_dict.list())} 件）",
        "supported": [
            "話者とスタイルの一覧",
            "テキストからのアクセント句生成",
            "ユーザー辞書（OpenJTalk の解析へ反映されます）",
            "複数音声の結合（connect_waves）",
            "まとめて合成（multi_synthesis）",
            "話速（speedScale）",
            "音量（volumeScale）",
            "前後の無音（prePhonemeLength / postPhonemeLength）",
            "読みが取れない行（記号だけの行・空行）※前後の無音ぶんの wav を返します",
            "出力サンプリングレートの変換",
            "ステレオ出力",
        ],
        "unsupported": [
            "モーラごとの音高・長さの編集（モデルが対応しません）",
            "音高（pitchScale）と抑揚（intonationScale）※ 対応する話者では有効です",
            "モーフィング合成",
            "歌唱合成",
            "AquesTalk 風記法",
        ],
    }
