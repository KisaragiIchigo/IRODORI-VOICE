"""エンジン設定の単一情報源。

設定は ``settings.json`` に永続化し、環境変数 ``IRODORI_VOICE_*`` で上書きできる。
デバイスと精度の ``auto`` 解決だけは実機の GPU を見て決めるため、torch を遅延 import する。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

from .paths import settings_file

DEFAULT_CHECKPOINT = "Aratako/Irodori-TTS-v4.1-Small"
MEANFLOW_CHECKPOINT = "Aratako/Irodori-TTS-v4.1-Small-MF"
DEFAULT_CODEC_REPO = "Aratako/Semantic-DACVAE-Japanese-32dim"

# Pascal 以前は bf16 のネイティブ演算器を持たず、変換コストだけが乗って fp32 より遅くなる。
MIN_BF16_COMPUTE_CAPABILITY = (8, 0)

# モデル本体は fp32 で約 2.9GB。codec と条件エンコーダを同居させる余裕を見て閾値を置く。
MIN_GPU_MEMORY_BYTES_FOR_MODEL = 6 * 1024**3

DeviceChoice = Literal["auto", "cuda", "cpu", "mps", "xpu"]
PrecisionChoice = Literal["auto", "fp32", "bf16"]
PronunciationMode = Literal["off", "kanji"]


@dataclass(frozen=True)
class DevicePlacement:
    """解決済みのデバイス配置。``auto`` を含まない確定値だけを持つ。"""

    model_device: str
    model_precision: str
    codec_device: str
    codec_precision: str
    reason: str


@dataclass
class EngineSettings:
    host: str = "127.0.0.1"
    port: int = 50121

    checkpoint: str = DEFAULT_CHECKPOINT
    codec_repo: str = DEFAULT_CODEC_REPO

    model_device: DeviceChoice = "auto"
    model_precision: PrecisionChoice = "auto"
    codec_device: DeviceChoice = "auto"
    codec_precision: PrecisionChoice = "auto"

    # サンプリング回数。所要時間はこの値にほぼ比例する。
    #
    # 実測（CPU / 音声長 7.78 秒）: 40 回で 57.6 秒、8 回で 7.3 秒、4 回で 6.0 秒。
    # 参照音声を使う話者は、スタイル側の指定がなければこの値で生成するため、
    # モデル推奨（通常の RF なら 40 回）のままでは待ち時間が実用にならない。
    #
    # None にするとチェックポイントの推奨値に従う（MeanFlow 版なら 4 回）。
    # 少ない回数で品質を保ちたい場合は、少ステップ生成向けに蒸留された
    # Aratako/Irodori-TTS-v4.1-Small-MF を checkpoint に指定して None へ戻す。
    num_steps: int | None = 8

    # 参照なし生成は試聴・声の固定・同梱話者で共通の品質条件を使う。
    # None は推論ランタイムの推奨値（標準40回、MeanFlow4回）を選ぶ。
    voice_design_steps: int | None = None

    # 長いテキストを自動で区切るか。Irodori-TTS は 1 回の合成で最大 30 秒までで、
    # 実測では 1 行 30〜40 文字のときに最も効率が良い（合成時間が音声長を下回る）。
    split_long_text: bool = True
    split_target_chars: int = 38
    split_max_chars: int = 60

    # 漢字を含む語を OpenJTalk の読みへ置き換えてからモデルへ渡すか。
    #
    # Irodori-TTS は表記からそのまま音を作るモデルで、漢字かな交じりの文章で学習して
    # いる。読みへ置き換えると、その語が何だったかという手がかりが消え、アクセントの
    # 置きどころが崩れる（実測: 「設定画面から生成回数を変更できます。」が
    # 「せっていがめんからせいせいかいすうをへんこうできます。」になる）。
    #
    # "off"   … 表記のまま渡す。抑揚は Irodori-TTS 本体と同じ条件になる。
    # "kanji" … 解析できた漢字語を読みへ置き換える。難しい語や固有名詞の読み違いを
    #           抑えられる代わりに、抑揚は崩れやすくなる。
    #
    # どちらでも、ユーザー辞書に登録した語の読み替えは効く。読みを直したい語が
    # 限られるなら、"off" のまま辞書へ登録する方が抑揚を保てる。
    pronunciation_mode: PronunciationMode = "off"

    # 感嘆詞だけが並ぶ行は息声になり、低域が普通の文の約 0.3 倍まで落ちる。
    # 合成後に不足分だけ持ち上げる。足りている行には掛からない。
    restore_low_band: bool = True

    warmup_on_start: bool = True
    warmup_text: str = "起動しました。"

    # 4GB 級の GPU では 2 つ目の常駐で必ず溢れるため、既定は 1。
    runtime_pool_size: int = 1
    audio_cache_entries: int = 256
    reference_latent_cache: bool = True

    prefetch_workers: int = 1

    enabled_backends: list[str] = field(default_factory=lambda: ["irodori", "aivm"])

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> EngineSettings:
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in raw.items() if k in known}
        return cls(**filtered)


def _env_override(settings: EngineSettings) -> EngineSettings:
    mapping: dict[str, str] = {
        "IRODORI_VOICE_HOST": "host",
        "IRODORI_VOICE_PORT": "port",
        "IRODORI_VOICE_CHECKPOINT": "checkpoint",
        "IRODORI_VOICE_MODEL_DEVICE": "model_device",
        "IRODORI_VOICE_MODEL_PRECISION": "model_precision",
        "IRODORI_VOICE_CODEC_DEVICE": "codec_device",
        "IRODORI_VOICE_CODEC_PRECISION": "codec_precision",
        "IRODORI_VOICE_NUM_STEPS": "num_steps",
    }
    updates: dict[str, Any] = {}
    for env_key, field_name in mapping.items():
        value = os.environ.get(env_key)
        if value is None or value == "":
            continue
        if field_name in ("port", "num_steps"):
            updates[field_name] = int(value)
        else:
            updates[field_name] = value
    if os.environ.get("IRODORI_VOICE_NO_WARMUP"):
        updates["warmup_on_start"] = False
    return replace(settings, **updates) if updates else settings


def load_settings() -> EngineSettings:
    path = settings_file()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            settings = EngineSettings.from_json(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            settings = EngineSettings()
    else:
        settings = EngineSettings()
    return _env_override(settings)


def save_settings(settings: EngineSettings) -> None:
    settings_file().write_text(
        json.dumps(settings.to_json(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _cuda_profile() -> tuple[bool, int, tuple[int, int]]:
    """(利用可否, 総 VRAM バイト数, compute capability) を返す。"""

    import torch

    if not torch.cuda.is_available():
        return False, 0, (0, 0)
    index = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(index)
    return True, int(props.total_memory), (int(props.major), int(props.minor))


def resolve_placement(settings: EngineSettings) -> DevicePlacement:
    """``auto`` を実機に合わせて確定値へ解決する。

    4GB 級の GPU にモデル本体を載せると VRAM 不足で落ちるため、容量が足りない場合は
    モデルを CPU へ退避し、比較的軽い codec だけ GPU に残す。
    """

    import torch

    has_cuda, vram, capability = _cuda_profile()
    reasons: list[str] = []

    if settings.model_device != "auto":
        model_device = settings.model_device
        reasons.append(f"モデルのデバイスは設定値 {model_device} を使用します。")
        # VRAM が足りないまま GPU を指定すると、CUDA は確保に失敗せずシステムメモリへ
        # 退避して動き続ける。PCIe 越しに重みを往復させるため、落ちる代わりに極端に
        # 遅くなる。GTX 1050 Ti（空き 2.5GB）へ 2.9GB のモデルを載せた実測では、
        # CPU の 6.0 秒に対して 36.2 秒（約 6 倍）かかった。
        if model_device == "cuda" and has_cuda and vram < MIN_GPU_MEMORY_BYTES_FOR_MODEL:
            reasons.append(
                f"ただし VRAM は {vram / 1024**3:.1f}GB しかなく、モデル本体（fp32 で約 2.9GB）"
                "には足りません。不足分をシステムメモリへ退避しながら動くため、CPU よりも"
                "大幅に遅くなります。設定を auto へ戻すことをおすすめします。"
            )
    elif has_cuda and vram >= MIN_GPU_MEMORY_BYTES_FOR_MODEL:
        model_device = "cuda"
        reasons.append(f"VRAM {vram / 1024**3:.1f}GB を検出したため、モデルを GPU で実行します。")
    elif has_cuda:
        model_device = "cpu"
        reasons.append(
            f"VRAM が {vram / 1024**3:.1f}GB しかないため、モデルは CPU で実行します。"
            "GPU に載せる場合は設定から明示的に cuda を選択してください。"
        )
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        model_device = "mps"
        reasons.append("Apple Silicon の MPS を使用します。")
    else:
        model_device = "cpu"
        reasons.append("利用可能な GPU が無いため CPU で実行します。")

    if settings.codec_device != "auto":
        codec_device = settings.codec_device
    elif has_cuda and model_device == "cpu" and vram > 0:
        # codec 単体なら 1GB 未満で収まるため、モデルを CPU に置いても GPU に残せる。
        codec_device = "cuda"
        reasons.append("codec は GPU に残して波形デコードを高速化します。")
    elif model_device in ("cuda", "mps", "xpu"):
        codec_device = model_device
    else:
        codec_device = "cpu"

    def _precision(choice: str, device: str) -> str:
        if choice != "auto":
            return choice
        if device not in ("cuda", "xpu"):
            return "fp32"
        if device == "cuda" and capability < MIN_BF16_COMPUTE_CAPABILITY:
            # model と codec の両方から呼ばれるため、同じ理由を二度並べない。
            note = (
                f"compute capability {capability[0]}.{capability[1]} は bf16 の"
                "ネイティブ演算に対応しないため fp32 を使用します。"
            )
            if note not in reasons:
                reasons.append(note)
            return "fp32"
        return "bf16"

    return DevicePlacement(
        model_device=model_device,
        model_precision=_precision(settings.model_precision, model_device),
        codec_device=codec_device,
        codec_precision=_precision(settings.codec_precision, codec_device),
        reason=" ".join(reasons),
    )
