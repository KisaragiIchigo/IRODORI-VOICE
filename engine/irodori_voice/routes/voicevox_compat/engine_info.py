"""エンジンの自己申告。

名乗り、対応する機器、できることとできないこと。エディタはこれを見て
コントロールの出し分けを決める。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...voicevox.accent import pyopenjtalk_available
from ...voicevox.icon import ENGINE_ICON_BASE64
from ...voicevox.manifest_docs import (
    DEPENDENCY_LICENSES,
    ENGINE_TERMS_OF_SERVICE,
    ENGINE_UPDATE_INFOS,
)
from ...voicevox.schemas import DEFAULT_OUTPUT_SAMPLING_RATE, SupportedDevices
from .shared import COMPAT_ENGINE_VERSION, ENGINE_UUID, engine_state, user_dict_store

router = APIRouter(tags=["voicevox-compat"])


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

    state = engine_state(request)
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
    state = engine_state(request)
    placement = state.placement
    return SupportedDevices(
        cpu=True,
        cuda=bool(placement is not None and placement.model_device == "cuda"),
        dml=False,
    )


@router.get("/core_versions", response_model=list[str])
def core_versions() -> list[str]:
    return [COMPAT_ENGINE_VERSION]


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
        "user_dict": user_dict_store.last_error or f"有効（登録語 {len(user_dict_store.list())} 件）",
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
