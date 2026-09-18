"""エンジンの状態・デバイス・設定。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from .. import __version__
from ..schemas import (
    BackendStatusOut,
    DeviceOut,
    HealthOut,
    SettingsOut,
    SettingsUpdateRequest,
)
from ..settings import resolve_placement, save_settings
from ..state import EngineState

router = APIRouter(tags=["system"])

# 変えると合成結果そのものが変わる設定。合成済みの音が残っていると、切り替えたのに
# 音が変わらないように見えるため、保存と同時に捨てる。
AUDIO_AFFECTING_SETTINGS = frozenset({"checkpoint", "num_steps", "pronunciation_mode"})


def _state(request: Request) -> EngineState:
    return request.app.state.engine


@router.get("/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    state = _state(request)
    return HealthOut(
        status=state.status,
        model_loaded=state.model_loaded,
        warmed_up=state.warmed_up,
        detail=state.detail,
        version=__version__,
    )


@router.get("/backends", response_model=list[BackendStatusOut])
def backends(request: Request) -> list[BackendStatusOut]:
    state = _state(request)
    if state.registry is None:
        return []
    return [
        BackendStatusOut(
            backend_id=item.backend_id,
            display_name=item.display_name,
            available=item.available,
            detail=item.detail,
            install_hint=item.install_hint,
        )
        for item in state.registry.availabilities()
    ]


@router.get("/devices", response_model=DeviceOut)
def devices(request: Request) -> DeviceOut:
    from ..vendor.irodori_tts.inference_runtime import list_available_runtime_devices

    state = _state(request)
    placement = state.placement
    if placement is None:
        placement = resolve_placement(state.settings)
    return DeviceOut(
        model_device=placement.model_device,
        model_precision=placement.model_precision,
        codec_device=placement.codec_device,
        codec_precision=placement.codec_precision,
        available_devices=list_available_runtime_devices(),
        reason=placement.reason,
    )


@router.get("/settings", response_model=SettingsOut)
def read_settings(request: Request) -> SettingsOut:
    settings = _state(request).settings
    return SettingsOut(
        checkpoint=settings.checkpoint,
        model_device=settings.model_device,
        model_precision=settings.model_precision,
        codec_device=settings.codec_device,
        codec_precision=settings.codec_precision,
        num_steps=settings.num_steps,
        pronunciation_mode=settings.pronunciation_mode,
        runtime_pool_size=settings.runtime_pool_size,
        reference_latent_cache=settings.reference_latent_cache,
        warmup_on_start=settings.warmup_on_start,
    )


@router.patch("/settings", response_model=SettingsOut)
def update_settings(request: Request, payload: SettingsUpdateRequest) -> SettingsOut:
    """設定を保存する。

    デバイスやチェックポイントの変更はモデルの再読み込みを伴うため、ここでは
    保存だけを行う。次回起動から反映される旨はエディタ側が案内する。
    """

    state = _state(request)
    changes = payload.model_dump(exclude_none=True)
    affects_audio = any(
        key in AUDIO_AFFECTING_SETTINGS and getattr(state.settings, key) != value
        for key, value in changes.items()
    )
    for key, value in changes.items():
        setattr(state.settings, key, value)
    save_settings(state.settings)
    if affects_audio and state.service is not None:
        state.service.clear_cache()
    return read_settings(request)
