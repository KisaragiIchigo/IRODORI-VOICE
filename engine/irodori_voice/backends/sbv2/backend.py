"""音声モデル（Style-Bert-VITS2）バックエンド。

Irodori-TTS が拡散モデルで品質を取りに行くのに対し、こちらは VITS2 系で
CPU でも実時間より速く回る。用途に応じて使い分けられるよう、同じ話者リストに並べる。

aivmlib と style-bert-vits2 は任意依存にしている。未導入でもエンジンは起動し、
``availability()`` が導入手順を返す。音声合成の主目的である Irodori-TTS が
重い依存の巻き添えで起動しなくなる方が損失が大きいため。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from ..base import (
    BackendAvailability,
    BackendError,
    SynthesisOutput,
    SynthesisParams,
    VoiceCapabilities,
    VoiceInfo,
    VoiceStyle,
)
from .metadata import (
    InstalledModel,
    model_reader_available,
    list_installed,
    style_bert_vits2_available,
)
from .punctuation_fix import apply_punctuation_fix

logger = logging.getLogger(__name__)

BACKEND_ID = "aivm"
VOICE_ID_PREFIX = "aivm:"

# Style-Bert-VITS2 が日本語処理に使う BERT。Hugging Face から取得する。
JP_BERT_REPO = "ku-nlp/deberta-v2-large-japanese-char-wwm"

# 話者の識別色はモデル側が持たないため、登録順にパレットを巡回させる。
COLOR_CYCLE = ("asagi", "wakatake", "fuji", "kobai", "rurikon", "yamabuki", "sumire", "shu")

SBV2_CAPABILITIES = VoiceCapabilities(
    speed=True,
    volume=True,
    pitch=True,
    intonation=True,
    caption=False,
    emoji_style=False,
    reference_audio=False,
    style_strength=True,
    # Style-Bert-VITS2 の infer はシードを受け取らない。揺らぎは noise 系が担う。
    seed=False,
    steps=False,
)


def preload_libraries() -> str | None:
    """遅延 import を起動時に済ませる。失敗した理由を返す（成功なら None）。

    transformers は属性アクセス時に実体を読み込む。合成要求を処理する
    ワーカースレッドから初めて import すると、途中で失敗した場合に
    不完全なモジュールが残り、以降ずっと ImportError になる。
    メインスレッドで一度通しておけばこの状態に入らない。

    失敗を握りつぶすと「使えない理由が分からないまま」になる。
    実行ファイル版では同梱漏れが原因になりやすく、例外の中身が唯一の手がかり。
    """

    try:
        from style_bert_vits2.nlp import bert_models  # noqa: F401
        from style_bert_vits2.tts_model import TTSModel  # noqa: F401
    except Exception as exc:
        logger.exception("style-bert-vits2 の事前読み込みに失敗しました")
        return f"{type(exc).__name__}: {exc}"

    apply_punctuation_fix()
    return None


def load_japanese_bert() -> None:
    """日本語 BERT を読み込む。

    キャッシュにあるならネットワークへ出ない。エンジンのプロセスから
    外部への接続が遮られている環境でも、取得済みなら合成できるようにする。
    取得していない場合だけオンラインで試す。
    """

    import os

    from style_bert_vits2.constants import Languages
    from style_bert_vits2.nlp import bert_models

    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        model = bert_models.load_model(Languages.JP, JP_BERT_REPO)
        bert_models.load_tokenizer(Languages.JP, JP_BERT_REPO)
        _align_dtype(model)
        return
    except Exception:
        pass
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous

    # キャッシュに無い。取得を試みる（約 1.3GB）。
    model = bert_models.load_model(Languages.JP, JP_BERT_REPO)
    bert_models.load_tokenizer(Languages.JP, JP_BERT_REPO)
    _align_dtype(model)


def _align_dtype(model) -> None:
    """BERT を fp32 に揃える。

    この BERT の config.json は torch_dtype: float16 を指定しているため、
    重みが fp32 でも transformers は fp16 へ変換して読み込む。
    Style-Bert-VITS2 本体は fp32 で動くので、そのまま渡すと
    「Input type (c10::Half) and bias type (float) should be the same」になる。
    """

    try:
        model.float()
    except AttributeError:
        pass


def _voice_id(model_uuid: str, speaker_local_id: int) -> str:
    return f"{VOICE_ID_PREFIX}{model_uuid}:{speaker_local_id}"


def _parse_voice_id(voice_id: str) -> tuple[str, int]:
    if not voice_id.startswith(VOICE_ID_PREFIX):
        raise BackendError(f"このバックエンドの話者 ID ではありません: {voice_id}")
    body = voice_id[len(VOICE_ID_PREFIX) :]
    model_uuid, _, raw_speaker = body.rpartition(":")
    if not model_uuid:
        raise BackendError(f"話者 ID の形式が不正です: {voice_id}")
    return model_uuid, int(raw_speaker)


class Sbv2Backend:
    backend_id = BACKEND_ID

    def __init__(self, *, device: str = "cpu") -> None:
        self._device = device
        self._lock = threading.Lock()
        self._models: dict[str, InstalledModel] = {}
        self._loaded: dict[str, Any] = {}
        # ワーカースレッドからの初回 import を避けるため、ここで通しておく。
        self._preload_error = preload_libraries()
        self.refresh()

    # ------------------------------------------------------------------ 状態

    def availability(self) -> BackendAvailability:
        missing: list[str] = []
        if not model_reader_available():
            missing.append("aivmlib")
        if not style_bert_vits2_available():
            missing.append("style-bert-vits2")

        if missing:
            return BackendAvailability(
                backend_id=BACKEND_ID,
                available=False,
                display_name="音声モデル",
                detail=f"未導入のライブラリがあります: {', '.join(missing)}",
                install_hint=f"pip install {' '.join(missing)}",
            )

        if self._preload_error is not None:
            return BackendAvailability(
                backend_id=BACKEND_ID,
                available=False,
                display_name="音声モデル",
                detail=f"style-bert-vits2 を読み込めませんでした: {self._preload_error}",
                install_hint="pip install --force-reinstall style-bert-vits2",
            )

        return BackendAvailability(
            backend_id=BACKEND_ID,
            available=True,
            display_name="音声モデル",
            detail=f"{len(self._models)} 個のモデルが登録されています（推論デバイス: {self._device}）",
        )

    def refresh(self) -> None:
        if not model_reader_available():
            self._models = {}
            return
        self._models = {model.uuid: model for model in list_installed()}

    # ------------------------------------------------------------------ 話者

    def list_voices(self) -> list[VoiceInfo]:
        """合成できる話者だけを返す。

        ONNX 形式（.aivmx）は取り込めても合成できない。一覧に出すと
        「選べるのに鳴らない」ことになるため、ここでは外す。
        モデル管理の一覧には出し、そちらで理由を伝える。
        """

        voices: list[VoiceInfo] = []
        for index, model in enumerate(self._models.values()):
            if model.is_onnx:
                continue
            for speaker in model.speakers:
                voices.append(
                    VoiceInfo(
                        voice_id=_voice_id(model.uuid, speaker.local_id),
                        backend_id=BACKEND_ID,
                        name=speaker.name,
                        description=model.description or f"{model.name}（{model.model_architecture}）",
                        color_key=COLOR_CYCLE[(index + speaker.local_id) % len(COLOR_CYCLE)],
                        styles=[
                            VoiceStyle(style_id=str(style.local_id), name=style.name)
                            for style in speaker.styles
                        ],
                        capabilities=SBV2_CAPABILITIES,
                        sample_rate=44100,
                        # モデルがアイコンを抱えていればそれを話者の画像にする。
                        # 利用者が別のアイコンを付けた場合は表示側で差し替わる。
                        portrait_path=str(speaker.icon_path) if speaker.icon_path else None,
                        is_builtin=False,
                    )
                )
        return voices

    def installed_models(self) -> list[InstalledModel]:
        return list(self._models.values())

    # ------------------------------------------------------------------ 合成

    def _ensure_model(self, model: InstalledModel):
        cached = self._loaded.get(model.uuid)
        if cached is not None:
            return cached

        from style_bert_vits2.tts_model import TTSModel

        if model.is_onnx:
            raise BackendError(
                f"{model.name} は ONNX 形式（.aivmx）です。"
                "現在導入されている style-bert-vits2 は PyTorch 形式にのみ対応しており、"
                "ONNX の推論には対応していません。"
                "同じ話者の .aivm（Safetensors 形式）を取り込んでください。",
                recoverable=False,
            )

        # Style-Bert-VITS2 は日本語の読みとアクセントの推定に BERT を使う。
        # 引数なしで呼ぶと同梱パス（site-packages/bert/...）だけを見に行き、
        # 用意されていなければ AssertionError で落ちるため、リポジトリ ID を明示する。
        load_japanese_bert()

        tts_model = TTSModel(
            model_path=model.model_path,
            config_path=model.config_path,
            style_vec_path=model.style_vectors_path,
            device=self._device,
        )
        tts_model.load()
        self._loaded[model.uuid] = tts_model
        return tts_model

    def synthesize(self, params: SynthesisParams) -> SynthesisOutput:
        if not style_bert_vits2_available():
            raise BackendError(
                "style-bert-vits2 が導入されていないため、このモデルを合成できません。",
                recoverable=False,
            )

        model_uuid, speaker_local_id = _parse_voice_id(params.voice_id)
        model = self._models.get(model_uuid)
        if model is None:
            raise BackendError(f"モデル {model_uuid} が登録されていません。")

        speaker = next(
            (s for s in model.speakers if s.local_id == speaker_local_id),
            None,
        )
        if speaker is None:
            raise BackendError(f"話者 {speaker_local_id} がモデル {model.name} に存在しません。")

        style_name = speaker.styles[0].name
        if params.style_id is not None:
            match = next((s for s in speaker.styles if str(s.local_id) == params.style_id), None)
            if match is not None:
                style_name = match.name

        with self._lock:
            tts_model = self._ensure_model(model)
            try:
                from style_bert_vits2.constants import Languages

                sample_rate, audio = tts_model.infer(
                    text=params.text,
                    language=Languages.JP,
                    speaker_id=speaker.local_id,
                    style=style_name,
                    style_weight=float(params.style_strength),
                    # length は「長さの倍率」。VOICEVOX の話速と向きが逆なので逆数を取る。
                    length=1.0 / max(0.1, float(params.speed)),
                    pitch_scale=1.0 + float(params.pitch),
                    intonation_scale=float(params.intonation),
                )
            except Exception as exc:
                raise BackendError(f"モデルでの合成に失敗しました: {exc}") from exc

        samples = np.asarray(audio)
        if samples.dtype == np.int16:
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = samples.astype(np.float32)
        if samples.ndim == 2:
            samples = samples.mean(axis=0 if samples.shape[0] < samples.shape[1] else 1)

        return SynthesisOutput(
            samples=np.ascontiguousarray(samples, dtype=np.float32),
            sample_rate=int(sample_rate),
            used_seed=0,
            stage_timings=[],
            notes=[],
        )

    # ------------------------------------------------------------- ライフサイクル

    def warmup(self) -> None:
        # モデルの実体が登録されていない状態でウォームアップする対象は無い。
        return

    def shutdown(self) -> None:
        with self._lock:
            self._loaded.clear()
