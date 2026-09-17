"""Irodori-TTS を共通バックエンドインターフェースへ適合させる層。

このクラスが持つ責務は 3 つだけに絞っている。

1. プリセット（話者 / スタイル）を ``SamplingRequest`` へ翻訳する
2. 参照音声の encode をキャッシュに逃がす
3. GPU を 1 本しか持たない前提で合成を直列化する

サンプリングそのものはベンダリング元の ``InferenceRuntime.synthesize`` に任せ、
ここでは一切書き換えない。上流の改善をそのまま取り込めるようにするため。
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

import numpy as np

from ...settings import DevicePlacement, EngineSettings
from ...vendor.irodori_tts.duration import ALLOWED_ANNOTATION_EMOJIS
from ...vendor.irodori_tts.inference_runtime import (
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
)
from ...voices.store import VoicePreset, VoicePresetStore, VoiceStyleDef
from ..base import (
    BackendAvailability,
    BackendError,
    SynthesisOutput,
    SynthesisParams,
    VoiceCapabilities,
    VoiceInfo,
    VoiceStyle,
)
from ...voicevox.user_dict import shared_user_dict
from .reading_overrides import apply_reading_overrides
from .symbol_filter import drop_unreadable_symbols
from .reference_cache import ReferenceLatentCache
from .runtime_pool import RuntimePool

BACKEND_ID = "irodori"
VOICE_ID_PREFIX = "irodori:"

# ウォームアップは初期化コストの先払いが目的なので、最小ステップで回す。
WARMUP_STEPS = 4

IRODORI_CAPABILITIES = VoiceCapabilities(
    speed=True,
    volume=True,
    # ピッチとイントネーションは Irodori-TTS の条件付けに対応物が無い。
    # 後段のリサンプリングで模倣すると声質が崩れるため、非対応として宣言する。
    pitch=False,
    intonation=False,
    caption=True,
    emoji_style=True,
    reference_audio=True,
    style_strength=True,
    seed=True,
    steps=True,
)


# 注釈絵文字の並びと、その直後に置かれた空白。
#
# 「😌🫶 こんにちは」のように絵文字と本文を空白で区切って書くのは自然だが、この空白は
# 読み上げ対象の文字としてモデルへ届き、声がこもる。実測（同梱話者・3 シード平均）では
# 空白の有無だけでスペクトル重心が 2076Hz と 3264Hz に分かれた。
#
# 全角空白は上流の正規化が落とすが、半角空白は残る。英文中の空白まで削ると読みが
# 壊れるため、絵文字の直後に限って落とす。
_EMOJI_RUN = "|".join(
    sorted((re.escape(mark) for mark in ALLOWED_ANNOTATION_EMOJIS), key=len, reverse=True)
)
_EMOJI_THEN_SPACE = re.compile(f"((?:{_EMOJI_RUN})+)[ 　]+")
_ANNOTATION_EMOJI = re.compile(_EMOJI_RUN)


def _apply_style_emoji(text: str, emoji: str | None) -> str:
    """スタイルの注釈絵文字を読み上げ文へ添える。

    本文に既に注釈絵文字がある場合は足さない。書き手が明示した指示の方が、
    スタイルに紐づく既定より意図が細かいため。長文が分割される場合は区間ごとに
    判定し、注釈のない区間にだけスタイルの指示を補う。
    """

    cleaned = _EMOJI_THEN_SPACE.sub(r"\1", text.strip())
    if emoji and not _ANNOTATION_EMOJI.search(cleaned):
        return f"{emoji}{cleaned}"
    return cleaned


def voice_id_for(preset: VoicePreset) -> str:
    return f"{VOICE_ID_PREFIX}{preset.preset_id}"


def preset_id_from(voice_id: str) -> str:
    if not voice_id.startswith(VOICE_ID_PREFIX):
        raise BackendError(f"Irodori バックエンドの話者 ID ではありません: {voice_id}")
    return voice_id[len(VOICE_ID_PREFIX) :]


class IrodoriBackend:
    backend_id = BACKEND_ID

    def __init__(
        self,
        *,
        settings: EngineSettings,
        placement: DevicePlacement,
        store: VoicePresetStore,
    ) -> None:
        self._settings = settings
        self._placement = placement
        self._store = store
        self._pool = RuntimePool(max_entries=settings.runtime_pool_size)
        self._reference_cache = ReferenceLatentCache(enabled=settings.reference_latent_cache)
        self._synthesis_lock = threading.Lock()
        self._load_error: str | None = None
        self._warmed_up = False
        self._sample_rate = 48000
        self._resolved_checkpoint: str | None = None

    # ------------------------------------------------------------------ 状態

    def _resolve_checkpoint(self) -> str:
        """設定値を実ファイルのパスへ解決する。

        ローカルパスならそのまま、Hugging Face のリポジトリ ID なら
        スナップショットを取得する。取得済みならキャッシュから即座に返るため、
        2 回目以降はネットワークに出ない。
        """

        if self._resolved_checkpoint is not None:
            return self._resolved_checkpoint

        raw = str(self._settings.checkpoint).strip()
        candidate = Path(raw)
        self._resolved_checkpoint = str(candidate) if candidate.exists() else download_hf_checkpoint(raw)
        return self._resolved_checkpoint

    def runtime_key(self, *, checkpoint: str | None = None) -> RuntimeKey:
        return RuntimeKey(
            checkpoint=checkpoint or self._resolve_checkpoint(),
            model_device=self._placement.model_device,
            codec_repo=self._settings.codec_repo,
            model_precision=self._placement.model_precision,
            codec_device=self._placement.codec_device,
            codec_precision=self._placement.codec_precision,
        )

    def availability(self) -> BackendAvailability:
        if self._load_error is not None:
            return BackendAvailability(
                backend_id=BACKEND_ID,
                available=False,
                display_name="Irodori-TTS",
                detail=self._load_error,
                install_hint="設定でチェックポイントとデバイスを確認してください。",
            )
        return BackendAvailability(
            backend_id=BACKEND_ID,
            available=True,
            display_name="Irodori-TTS",
            detail=(
                f"{self._settings.checkpoint} / モデル {self._placement.model_device}"
                f" ({self._placement.model_precision})"
                f" / codec {self._placement.codec_device}"
            ),
        )

    @property
    def is_loaded(self) -> bool:
        # チェックポイント未解決のうちは、問い合わせのためだけに取得を走らせない。
        if self._resolved_checkpoint is None:
            return False
        return self._pool.is_loaded(self.runtime_key(checkpoint=self._resolved_checkpoint))

    @property
    def is_warmed_up(self) -> bool:
        return self._warmed_up

    # ------------------------------------------------------------------ 話者

    def list_voices(self) -> list[VoiceInfo]:
        voices: list[VoiceInfo] = []
        for preset in self._store.list():
            voices.append(
                VoiceInfo(
                    voice_id=voice_id_for(preset),
                    backend_id=BACKEND_ID,
                    name=preset.name,
                    description=preset.description,
                    color_key=preset.color_key,
                    styles=[
                        VoiceStyle(style_id=style.style_id, name=style.name, emoji=style.emoji)
                        for style in preset.styles
                    ],
                    capabilities=IRODORI_CAPABILITIES,
                    sample_rate=self._sample_rate,
                    portrait_path=preset.portrait_path(),
                    is_builtin=preset.builtin,
                    voice_seed=preset.voice_seed,
                    has_reference=preset.mode == "reference" and bool(preset.reference_files),
                )
            )
        return voices

    # ------------------------------------------------------------------ 合成

    def synthesize(self, params: SynthesisParams) -> SynthesisOutput:
        try:
            preset = self._store.get(preset_id_from(params.voice_id))
            style = preset.style(params.style_id)
        except KeyError as exc:
            # 話者やスタイルが見つからないのは要求側で直せる誤り。ここで
            # BackendError に translate しないと、HTTP 層まで KeyError が
            # 抜けて 500 になり、エディタに理由が出ない。
            raise BackendError(str(exc.args[0]) if exc.args else str(exc)) from exc

        with self._synthesis_lock:
            runtime, newly_loaded = self._acquire_runtime()

            request = self._build_request(params=params, preset=preset, style=style, runtime=runtime)

            started = time.perf_counter()
            try:
                result = runtime.synthesize(request)
            except (ValueError, RuntimeError) as exc:
                raise BackendError(f"合成に失敗しました: {exc}") from exc
            elapsed = time.perf_counter() - started

        audio = result.audio.detach().cpu().float().numpy()
        if audio.ndim == 2:
            audio = audio.mean(axis=0)
        samples = np.ascontiguousarray(audio, dtype=np.float32)

        timings = list(result.stage_timings)
        timings.append(("total", elapsed))
        notes = list(result.messages)
        if newly_loaded:
            notes.append("モデルを読み込みました。次回以降の合成はこの待ち時間がなくなります。")

        return SynthesisOutput(
            samples=samples,
            sample_rate=int(result.sample_rate),
            used_seed=int(result.used_seed),
            stage_timings=timings,
            notes=notes,
        )

    def _acquire_runtime(self):
        try:
            runtime, newly_loaded = self._pool.acquire(self.runtime_key())
        except Exception as exc:
            self._load_error = f"モデルを読み込めませんでした: {exc}"
            raise BackendError(self._load_error, recoverable=False) from exc
        self._load_error = None
        self._sample_rate = int(runtime.codec.sample_rate)
        return runtime, newly_loaded

    def _build_request(
        self,
        *,
        params: SynthesisParams,
        preset: VoicePreset,
        style: VoiceStyleDef,
        runtime,
    ) -> SamplingRequest:
        # VOICEVOX の「話速」は大きいほど速い。Irodori の duration_scale は
        # 大きいほど長い（= 遅い）ので、逆数を取って向きを合わせる。
        speed = max(0.1, float(params.speed))
        duration_scale = float(style.duration_scale) / speed

        # スタイル強度はキャプション条件の効き具合として表現する。
        caption_scale = float(style.cfg_scale_caption) * max(0.0, float(params.style_strength))

        caption = params.caption if params.caption is not None else style.caption
        if caption is not None and caption.strip() == "":
            caption = None

        # 読みの指定はモデルへ渡せないため、辞書の登録語は表記の側で当てる。
        text = apply_reading_overrides(params.text, shared_user_dict().reading_overrides())
        # 登録語を当てたあとに掛ける。辞書へ入れた記号は既に読みへ変わっているため、
        # ここで落ちるのは登録されていない記号だけになる。
        text = drop_unreadable_symbols(text)
        text = _apply_style_emoji(text, style.emoji)

        cfg_scale_text = float(style.cfg_scale_text)
        if preset.mode == "caption":
            # 参照音声なし（シード）の場合はAIの幻覚が暴走しやすく、ひらがなや辞書指定を無視しがち。
            # テキスト条件の拘束力（cfg_scale_text）を強制的に底上げして、辞書への食いつきを改善する。
            cfg_scale_text = max(cfg_scale_text, 5.0)

        request = SamplingRequest(
            text=text,
            caption=caption,
            seconds=None,
            duration_scale=duration_scale,
            cfg_scale_text=cfg_scale_text,
            cfg_scale_caption=caption_scale,
            cfg_scale_speaker=float(style.cfg_scale_speaker),
            # プリセットにシードが設定されていれば、要求の指定より優先する。
            # 「この声」と決めて保存した話者は、常にその声で鳴らなければならない。
            seed=preset.voice_seed if preset.voice_seed is not None else params.seed,
            num_steps=params.steps if params.steps is not None else self._settings.num_steps,
        )

        if preset.mode == "caption":
            request.no_ref = True
            return request

        if preset.mode == "embed":
            embed_path = preset.speaker_embed_path()
            if embed_path is None:
                raise BackendError(f"話者 {preset.name} に話者埋め込みが設定されていません。")
            request.ref_embed = embed_path
            return request

        wav_paths = preset.reference_paths()
        if not wav_paths:
            raise BackendError(f"話者 {preset.name} に参照音声が設定されていません。")

        cached = self._reference_cache.resolve(
            wav_paths,
            runtime=runtime,
            normalize_db=request.ref_normalize_db,
            ensure_max=request.ref_ensure_max,
            max_ref_seconds=request.max_ref_seconds,
        )
        if cached:
            request.ref_latents = cached
        else:
            request.ref_wavs = wav_paths
        return request

    # ------------------------------------------------------------- ライフサイクル

    def warmup(self) -> None:
        """起動直後に 1 回だけ短い合成を流し、初回のカーネル構築コストを先払いする。

        狙いは重みの読み込みとカーネルの初期化を済ませることなので、サンプリングは
        最小回数で足りる。既定のステップ数で回すと、それだけで数十秒を待つことになる。
        """

        if self._warmed_up:
            return
        preset = next((p for p in self._store.list() if p.mode == "caption"), None)
        if preset is None:
            self._warmed_up = True
            return
        try:
            self.synthesize(
                SynthesisParams(
                    text=self._settings.warmup_text,
                    voice_id=voice_id_for(preset),
                    style_id=preset.styles[0].style_id,
                    seed=0,
                    post_silence=0.0,
                    steps=WARMUP_STEPS,
                )
            )
        except BackendError:
            # ウォームアップの失敗そのものは致命ではない。実合成時に同じ例外が出て報告される。
            pass
        self._warmed_up = True

    def shutdown(self) -> None:
        self._pool.evict_all()
        self._warmed_up = False
