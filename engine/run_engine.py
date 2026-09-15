"""IRODORI-VOICE エンジンの起動エントリ。

    python run_engine.py --port 50121

エディタ（デスクトップシェル）は、このスクリプトを子プロセスとして起動し、
``/health`` が ``ready`` を返すまで「準備中」を表示する運用を想定している。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from irodori_voice.app import create_app  # noqa: E402
from irodori_voice.settings import load_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="IRODORI-VOICE エンジン")
    parser.add_argument("--host", default=settings.host, help="待ち受けホスト")
    parser.add_argument("--port", type=int, default=settings.port, help="待ち受けポート")
    parser.add_argument(
        "--editor-dist",
        default=None,
        help=(
            "ビルド済みの Web UI を同一オリジンで配信する場合に、その dist "
            "ディレクトリを指定します。省略時は配信しません。"
        ),
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="起動時のモデル読み込みとウォームアップを行いません。",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="アクセスログを出力しません。",
    )
    parser.add_argument(
        "--use_gpu",
        action="store_true",
        help=(
            "VOICEVOX エディタが GPU モードのときに付けてくる引数です。"
            "このエンジンは VRAM を見てデバイスを自分で決めるため、値は使いません。"
            "GPU へ載せる場合は設定の model_device / codec_device に cuda を指定してください。"
        ),
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="依存ライブラリの読み込みを順に試し、結果を表示して終了します。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.diagnose:
        from irodori_voice.diagnostics import format_report, run_checks

        print(format_report(run_checks()))
        return 0

    if args.no_warmup:
        import os

        os.environ["IRODORI_VOICE_NO_WARMUP"] = "1"

    if args.use_gpu:
        # 受け取るが従わない。黙って無視すると「GPU にしたのに速くならない」の
        # 原因が見えなくなるため、判断の置き場所をここで伝える。
        print(
            "--use_gpu を受け取りました。デバイスは VRAM を見て自動で決めるため、"
            "この指定では切り替わりません。GPU を使う場合は設定の model_device に "
            "cuda を指定してください。"
        )

    # 画面の配信は --editor-dist を明示したときだけ行う。
    # VOICEVOX エディタを使う構成では、エンジンのルートで別の UI を配信すると
    # どちらを操作しているのか分からなくなる。
    editor_dist = Path(args.editor_dist).resolve() if args.editor_dist else None

    import uvicorn

    app = create_app(editor_dist=editor_dist)
    # アクセスログは既定で出す。エディタや外部ツールからの接続を切り分けるとき、
    # どのエンドポイントが何を返したかが見えないと原因にたどり着けない。
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
