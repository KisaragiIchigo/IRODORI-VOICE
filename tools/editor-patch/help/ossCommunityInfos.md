# ソフトウェアの構成

本ソフトウェアは、独立した 2 つのプロセスと、外部のオープンソースソフトウェアを組み合わせて動いています。どこで何が起きているかを把握しておくと、不具合の切り分けが容易になります。

## IRODORI-VOICE Engine

Python と FastAPI で書かれた常駐プロセスです。既定では `127.0.0.1:50121` で待ち受け、VOICEVOX ENGINE 互換の API を提供します。音声合成、日本語の解析、話者の管理、音声モデルの取り込みを担当します。

内部には 2 つの合成バックエンドがあります。

- **Irodori-TTS バックエンド** — Flow Matching による音声合成です。読み上げ文をそのままモデルへ渡し、参照音声・キャプション・シードで声と話し方を決めます。
- **モデルバックエンド** — 取り込んだ音声モデルによる合成です。モーラ単位の読みとアクセントを扱います。

## VOICEVOX エディター

読み上げ画面です。[VOICEVOX 公式リポジトリ](https://github.com/VOICEVOX/voicevox)のものを各自の環境で取得し、接続先をこのエンジンへ向けて使用しています。エディタを自作していないため、VOICEVOX で覚えた操作、辞書、台本がそのまま通用します。

本ソフトウェア向けの改変は、同梱の `tools/patch-editor.mjs` が置換として当てています。改変済みのエディタを同梱して配布する形は取っていません。

## 管理画面

エンジンが `http://127.0.0.1:50121/admin` で配信している画面です。音声モデルの取り込み、話者の作成、合成モデルの切り替えを行います。読み上げの操作はエディタ、素材の準備は管理画面、と役割を分けています。メニューの「エンジン」→「音声モデルの管理」から開けます。

## 利用しているソフトウェア

| 名称 | 役割 |
| --- | --- |
| [VOICEVOX](https://github.com/VOICEVOX/voicevox) | 読み上げ画面 |
| [Irodori-TTS](https://github.com/Aratako/Irodori-TTS) | Flow Matching による音声合成 |
| [Style-Bert-VITS2](https://github.com/litagin02/Style-Bert-VITS2) | 取り込んだ音声モデルの合成 |
| [aivmlib](https://github.com/Aivis-Project/aivmlib) | モデルファイルの読み込み |
| [pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus) | 日本語の読みとアクセントの解析 |

ライセンスの詳細は「ソフトウェアの利用規約」および「ライセンス情報」をご覧ください。
