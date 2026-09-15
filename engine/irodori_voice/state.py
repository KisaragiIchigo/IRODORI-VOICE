"""エンジン全体の起動状態。

起動を速く見せるための肝がここにある。HTTP サーバーは即座に応答を開始し、
2.9GB のモデル読み込みとウォームアップは別スレッドへ逃がす。エディタは
``/health`` を見て「準備中」を出しながら、テキスト入力や話者選択を先に触れる。
"""

from __future__ import annotations

import threading

from .backends.sbv2.backend import Sbv2Backend
from .backends.base import BackendError
from .backends.irodori.backend import IrodoriBackend
from .backends.registry import BackendRegistry, SynthesisService
from .settings import DevicePlacement, EngineSettings, load_settings, resolve_placement
from .voices.presets import BUILTIN_PRESETS
from .voicevox.sample_voice import sample_store
from .voices.store import VoicePresetStore


class EngineState:
    def __init__(self) -> None:
        self.settings: EngineSettings = load_settings()
        self.placement: DevicePlacement | None = None
        self.store: VoicePresetStore | None = None
        self.irodori: IrodoriBackend | None = None
        self.aivm: Sbv2Backend | None = None
        self.registry: BackendRegistry | None = None
        self.service: SynthesisService | None = None

        self._error: str | None = None
        self._loader_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------- 構築

    def bootstrap(self) -> None:
        """HTTP を受け付けられる状態まで組み立てる。モデル本体はまだ読まない。"""

        self.store = VoicePresetStore(BUILTIN_PRESETS)
        self.placement = resolve_placement(self.settings)

        self.irodori = IrodoriBackend(
            settings=self.settings,
            placement=self.placement,
            store=self.store,
        )
        # こちらの推論は VITS2 系で軽く、CPU でも実用速度が出る。VRAM を奪い合うと
        # Irodori 側が確保に失敗するため、Irodori が GPU に載っている間は CPU に置く。
        if self.placement.model_device == "cuda":
            aivm_device = "cpu"
        elif self.placement.codec_device == "cuda":
            aivm_device = "cuda"
        else:
            aivm_device = "cpu"
        self.aivm = Sbv2Backend(device=aivm_device)

        backends = []
        if "irodori" in self.settings.enabled_backends:
            backends.append(self.irodori)
        if "aivm" in self.settings.enabled_backends:
            backends.append(self.aivm)

        self.registry = BackendRegistry(backends)
        self.service = SynthesisService(
            self.registry,
            cache_entries=self.settings.audio_cache_entries,
        )
        self.service.start_prefetch_worker()

        # 話者一覧の試聴音声は、要求された時点で作り置きが無ければ裏で生成する。
        sample_store.bind(self._generate_sample)

    def start_background_load(self) -> None:
        """モデル読み込みとウォームアップを別スレッドで進める。"""

        if not self.settings.warmup_on_start or self.irodori is None:
            return
        with self._lock:
            if self._loader_thread is not None:
                return
            thread = threading.Thread(
                target=self._load_and_warm,
                name="irodori-voice-warmup",
                daemon=True,
            )
            self._loader_thread = thread
            thread.start()

    def _load_and_warm(self) -> None:
        try:
            assert self.irodori is not None
            self.irodori.warmup()
        except BackendError as exc:
            self._error = str(exc)
        except Exception as exc:  # noqa: BLE001 - 起動時の想定外もここで握って状態に残す
            self._error = f"ウォームアップ中に想定外のエラーが発生しました: {exc}"

    # ------------------------------------------------------------- 状態

    @property
    def status(self) -> str:
        if self._error is not None:
            return "error"
        if self.irodori is not None and self.irodori.is_warmed_up:
            return "ready"
        if not self.settings.warmup_on_start:
            return "ready"
        return "starting"

    @property
    def detail(self) -> str:
        if self._error is not None:
            return self._error
        if self.placement is None:
            return "初期化中です。"
        if self.status == "starting":
            return f"モデルを読み込んでいます。{self.placement.reason}"
        return self.placement.reason

    @property
    def model_loaded(self) -> bool:
        return self.irodori is not None and self.irodori.is_loaded

    @property
    def warmed_up(self) -> bool:
        return self.irodori is not None and self.irodori.is_warmed_up

    def _generate_sample(self, voice_id: str, style_id: str | None, text: str) -> bytes:
        """試聴用の短い音声を作る。

        分割は不要な長さなので通さず、話者固定のシードで合成する。
        一覧に並ぶ声と実際に合成される声を一致させるため。
        """

        from .backends.base import SynthesisParams
        from .synthesis.pipeline import (
            LowBandPolicy,
            OutputFormat,
            SplitPolicy,
            synthesize_pipeline,
        )

        if self.service is None:
            raise RuntimeError("エンジンが初期化されていません。")

        result = synthesize_pipeline(
            SynthesisParams(
                text=text,
                voice_id=voice_id,
                style_id=style_id,
                post_silence=0.05,
            ),
            synthesize_segment=self.service.synthesize,
            split=SplitPolicy(enabled=False),
            output=OutputFormat(),
            low_band=LowBandPolicy(enabled=self.settings.restore_low_band),
        )
        return result.audio.wav

    def clear_error(self) -> None:
        self._error = None

    def shutdown(self) -> None:
        if self.service is not None:
            self.service.shutdown()
