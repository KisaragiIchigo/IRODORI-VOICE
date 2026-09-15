"""エンジンの自己診断。

    python run_engine.py --diagnose
    irodori-voice-engine.exe --diagnose

実行ファイル版では、開発環境では通っていた import が同梱漏れで失敗することがある。
その場合ふつうは「モデルを読み込めませんでした」のような要約しか表に出ず、
本当の原因（どのモジュールが、なぜ）が分からない。ここでは各依存を順に試し、
失敗したものについてはトレースバックをそのまま出す。

チェックは互いに独立した純粋な関数として並べ、``run_checks`` は順に呼ぶだけにする。
依存を 1 つ増やすときは関数を 1 つ足して ``CHECKS`` に並べる。
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    traceback_text: str | None = None


def _failed(name: str, exc: BaseException) -> CheckResult:
    return CheckResult(
        name=name,
        ok=False,
        detail=f"{type(exc).__name__}: {exc}",
        traceback_text="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def check_runtime() -> CheckResult:
    frozen = getattr(sys, "frozen", False)
    base = getattr(sys, "_MEIPASS", None)
    detail = f"Python {sys.version.split()[0]} / 実行ファイル版: {'はい' if frozen else 'いいえ'}"
    if base:
        detail += f" / 同梱ディレクトリ: {base}"
    return CheckResult(name="実行環境", ok=True, detail=detail)


def check_torch() -> CheckResult:
    try:
        import torch

        return CheckResult(
            name="torch",
            ok=True,
            detail=f"{torch.__version__} / CUDA: {'利用可' if torch.cuda.is_available() else '無し'}",
        )
    except Exception as exc:
        return _failed("torch", exc)


def check_transformers() -> CheckResult:
    """ModernBERT のクラスまで実際に解決させる。

    transformers はパッケージ内の .py を実行時に走査して import 構造を組み立てる。
    ソースが同梱されていないと、名前は見えていても実体へたどり着けない。
    """

    try:
        import transformers

        model_class = transformers.ModernBertModel
        return CheckResult(
            name="transformers",
            ok=True,
            detail=f"{transformers.__version__} / {model_class.__name__} を解決できました",
        )
    except Exception as exc:
        return _failed("transformers", exc)


def check_pyopenjtalk() -> CheckResult:
    """辞書を読んでラベルを 1 つ取り出せるところまで確かめる。"""

    try:
        import pyopenjtalk

        labels = pyopenjtalk.extract_fullcontext("日本語")
        dictionary = pyopenjtalk.OPEN_JTALK_DICT_DIR
        if isinstance(dictionary, bytes):
            dictionary = dictionary.decode("utf-8", "replace")
        return CheckResult(
            name="pyopenjtalk",
            ok=True,
            detail=f"ラベル {len(labels)} 行 / 辞書: {dictionary}",
        )
    except Exception as exc:
        return _failed("pyopenjtalk", exc)


def check_accent_phrases() -> CheckResult:
    """アクセント句が細かく割れているかを見る。

    1 句しか出ない場合はラベル解析が動いておらず、カタカナの代替に落ちている。
    """

    from .voicevox import accent

    sample = "バランスは、明確に高い結果です。"
    try:
        phrases = accent.build_accent_phrases(sample)
    except Exception as exc:
        return _failed("アクセント句", exc)

    readings = " / ".join("".join(mora.text for mora in phrase.moras) for phrase in phrases)
    if accent.last_fallback_reason is not None:
        return CheckResult(
            name="アクセント句",
            ok=False,
            detail=f"代替に落ちています（{accent.last_fallback_reason}）: {readings}",
        )
    return CheckResult(
        name="アクセント句",
        ok=True,
        detail=f"{len(phrases)} 句: {readings}",
    )


def check_style_bert_vits2() -> CheckResult:
    try:
        from .backends.sbv2.backend import preload_libraries
    except Exception as exc:
        return _failed("style-bert-vits2", exc)

    reason = preload_libraries()
    if reason is None:
        return CheckResult(name="style-bert-vits2", ok=True, detail="読み込めました")
    return CheckResult(name="style-bert-vits2", ok=False, detail=reason)


def check_aivmlib() -> CheckResult:
    try:
        import aivmlib

        return CheckResult(
            name="aivmlib",
            ok=True,
            detail=getattr(aivmlib, "__version__", "バージョン不明"),
        )
    except Exception as exc:
        return _failed("aivmlib", exc)


def check_codec() -> CheckResult:
    try:
        import dacvae
        import soundfile

        return CheckResult(
            name="音声コーデック",
            ok=True,
            detail=f"dacvae / soundfile {soundfile.__version__}",
        )
    except Exception as exc:
        return _failed("音声コーデック", exc)


CHECKS: tuple[Callable[[], CheckResult], ...] = (
    check_runtime,
    check_torch,
    check_transformers,
    check_pyopenjtalk,
    check_accent_phrases,
    check_style_bert_vits2,
    check_aivmlib,
    check_codec,
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in CHECKS:
        try:
            results.append(check())
        except Exception as exc:
            results.append(_failed(getattr(check, "__name__", "不明な項目"), exc))
    return results


def format_report(results: list[CheckResult]) -> str:
    lines = ["IRODORI-VOICE エンジン 自己診断", ""]
    for result in results:
        lines.append(f"[{'OK' if result.ok else 'NG'}] {result.name}: {result.detail}")

    failures = [result for result in results if not result.ok and result.traceback_text]
    if failures:
        lines.append("")
        lines.append("失敗した項目のトレースバック")
        for result in failures:
            lines.append("")
            lines.append(f"--- {result.name} ---")
            lines.append(result.traceback_text.rstrip())

    return "\n".join(lines)
