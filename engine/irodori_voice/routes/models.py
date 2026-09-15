"""チェックポイントの切り替え。

MeanFlow 版（少ステップ生成向けに蒸留されたもの）への切り替えを、
設定ファイルを直接編集せずに行えるようにする。

切り替えはモデルの再読み込みを伴うため、ここでは設定の保存までを行い、
実際の読み込みは次回の合成時に発生する。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..settings import DEFAULT_CHECKPOINT, MEANFLOW_CHECKPOINT, save_settings
from ..state import EngineState

router = APIRouter(prefix="/models", tags=["models"])

# 既知のチェックポイントと、その特性。
KNOWN_CHECKPOINTS: dict[str, dict[str, object]] = {
    DEFAULT_CHECKPOINT: {
        "label": "標準（v4.1-Small）",
        "recommended_steps": 8,
        "detail": (
            "通常の Rectified Flow。モデル推奨は 40 回ですが、待ち時間との釣り合いから "
            "8 回を既定にしています。回数を減らすと品質が落ちます。"
        ),
    },
    MEANFLOW_CHECKPOINT: {
        "label": "高速（v4.1-Small-MF / MeanFlow 蒸留）",
        "recommended_steps": None,
        "detail": (
            "4 回生成を前提に蒸留された版です。少ない回数でも品質が保たれるため、"
            "サンプリング回数はモデル推奨（4 回）に任せられます。"
        ),
    },
}


def _state(request: Request) -> EngineState:
    return request.app.state.engine


def _is_downloaded(checkpoint: str) -> bool:
    """Hugging Face のキャッシュに取得済みかを調べる。

    取得済みなら切り替えが即座に効く。未取得なら初回の合成で
    ダウンロードが走り、数分待たされる。
    """

    if Path(checkpoint).exists():
        return True
    cache = Path.home() / ".cache/huggingface/hub"
    folder = "models--" + checkpoint.replace("/", "--")
    snapshots = cache / folder / "snapshots"
    if not snapshots.is_dir():
        return False
    return any((item / "model.safetensors").is_file() for item in snapshots.iterdir())


@router.get("")
def list_checkpoints(request: Request) -> dict:
    """選べるチェックポイントと、現在の選択を返す。"""

    settings = _state(request).settings
    return {
        "current": settings.checkpoint,
        "current_steps": settings.num_steps,
        "checkpoints": [
            {
                "checkpoint": name,
                "label": info["label"],
                "detail": info["detail"],
                "recommended_steps": info["recommended_steps"],
                "downloaded": _is_downloaded(name),
                "selected": name == settings.checkpoint,
            }
            for name, info in KNOWN_CHECKPOINTS.items()
        ],
    }


@router.post("/select")
def select_checkpoint(request: Request, checkpoint: str, steps: int | None = None) -> dict:
    """チェックポイントを切り替える。

    既知のものを選んだ場合は、推奨のサンプリング回数も併せて設定する。
    反映にはエンジンの再起動が必要。
    """

    state = _state(request)
    known = KNOWN_CHECKPOINTS.get(checkpoint)
    if known is None and not Path(checkpoint).exists() and "/" not in checkpoint:
        raise HTTPException(
            status_code=422,
            detail=(
                "未知のチェックポイントです。Hugging Face のリポジトリ ID か、"
                "ローカルの safetensors へのパスを指定してください。"
            ),
        )

    state.settings.checkpoint = checkpoint
    if steps is not None:
        state.settings.num_steps = steps
    elif known is not None:
        state.settings.num_steps = known["recommended_steps"]  # type: ignore[assignment]
    save_settings(state.settings)

    return {
        "checkpoint": state.settings.checkpoint,
        "num_steps": state.settings.num_steps,
        "downloaded": _is_downloaded(checkpoint),
        "restart_required": True,
        "detail": "設定を保存しました。エンジンを再起動すると反映されます。",
    }
