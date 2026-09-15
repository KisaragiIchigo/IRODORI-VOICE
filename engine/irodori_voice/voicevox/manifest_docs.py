"""``engine_manifest`` が返す文面。

エディタのヘルプは、この 3 つをそれぞれ独立したページとして表示する。ルーティングとは
変更の理由が違う（文面の更新と API の実装は別物）ため、voicevox_compat.py から分けている。

利用規約はエディタ側の「ソフトウェアの利用規約」とは別のページに出る。そちらを読んで
いない利用者もいるため、エンジン単体で読んで意味が通る形で書いている。
"""

from __future__ import annotations

from typing import Any

# エディタは Markdown として描画する。
ENGINE_TERMS_OF_SERVICE = """\
# IRODORI-VOICE Engine 利用規約

このエンジンは、Irodori-TTS による音声合成を、VOICEVOX ENGINE 互換の
API として提供します。個人が制作したものであり、VOICEVOX の公式エンジンではありません。

## 合成した音声の利用について

**このエンジンは、合成した音声の利用条件を定めません。** 利用条件を決めるのは、その音声を
出した音声モデルの配布元です。ヘルプの「音声ライブラリの利用規約」で、お使いのモデルの
条件をご確認ください。

参照音声を持たない話者（シード値から作った話者）の声は、Irodori-TTS が学習した範囲から
生成されたもので、特定の人物の声を再現するものではありません。

他人の声を参照音声として登録する場合は、その人の許諾を得てください。このエンジンは許諾の
有無を確認しません。

## 電子透かし

合成した音声には、Irodori-TTS の推論コードが SilentCipher による電子透かしを付与します。
聴感には影響しません。取り除いての使用は想定していません。

## 通信について

エンジンは `127.0.0.1` のみで待ち受けます。外部からの接続は受け付けず、読み上げたテキストや
合成した音声を外部へ送信することもありません。

ただし、次の場合に限り外部へ接続します。いずれも取得後はローカルに保存され、以後は接続しません。

- 音声合成モデルが手元に無い場合、Hugging Face から取得します
- Style-Bert-VITS2 が読みの解析に使う言語モデルを、初回の合成時に取得します

## 免責事項

このエンジンは現状有姿で提供されます。制作者は、動作、合成結果の品質、特定目的への適合性に
ついて、いかなる保証も行いません。使用によって生じた損害について、制作者は責任を負いません。

## 構成

推論コードは Irodori-TTS（MIT）をベンダリングしたもので、サンプリング処理そのものは
書き換えていません。任意の追加依存として Style-Bert-VITS2（**AGPL-3.0**）を使う構成もあります。
各構成要素のライセンスは「ライセンス情報」のページをご覧ください。
"""


def _license(name: str, license_name: str, text: str, version: str = "") -> dict[str, Any]:
    return {"name": name, "version": version, "license": license_name, "text": text}


# ライセンス全文ではなく、役割と入手先を示す。全文は各配布元にある。
DEPENDENCY_LICENSES: list[dict[str, Any]] = [
    _license(
        "Irodori-TTS",
        "MIT",
        "Flow Matching による音声合成の推論コードです。エンジンへベンダリングして使用して"
        "います。\nhttps://github.com/Aratako/Irodori-TTS",
        version="v4.1",
    ),
    _license(
        "Style-Bert-VITS2",
        "AGPL-3.0",
        "任意の追加依存です。導入しない構成では読み込まれません。"
        "\nAGPL-3.0 は、改変したものをネットワーク越しのサービスとして提供する場合に、"
        "ソースの開示を求めるライセンスです。\nhttps://github.com/litagin02/Style-Bert-VITS2",
    ),
    _license(
        "aivmlib",
        "MIT",
        "モデルファイルの読み込みと検証に使用しています。"
        "\nhttps://github.com/Aivis-Project/aivmlib",
    ),
    _license(
        "pyopenjtalk-plus",
        "MIT",
        "日本語の読みとアクセントの解析に使用しています。内部の OpenJTalk および HTS Engine は"
        " Modified BSD ライセンスです。\nhttps://github.com/tsukumijima/pyopenjtalk-plus",
    ),
    _license(
        "SilentCipher",
        "MIT",
        "合成した音声への電子透かしの付与に使用しています。Copyright (c) 2024 Sony Research Inc."
        "\nhttps://github.com/sony/silentcipher",
    ),
    _license(
        "PyTorch",
        "BSD-3-Clause",
        "モデルの推論を実行しています。\nhttps://github.com/pytorch/pytorch",
    ),
    _license(
        "Transformers",
        "Apache-2.0",
        "テキストのトークン化と、読みの解析に使う言語モデルの読み込みに使用しています。"
        "\nhttps://github.com/huggingface/transformers",
    ),
    _license(
        "Hugging Face Hub",
        "Apache-2.0",
        "モデルの取得とキャッシュに使用しています。\nhttps://github.com/huggingface/huggingface_hub",
    ),
    _license(
        "safetensors",
        "Apache-2.0",
        "モデルの重みの読み書きに使用しています。\nhttps://github.com/huggingface/safetensors",
    ),
    _license(
        "FastAPI",
        "MIT",
        "HTTP API の提供に使用しています。\nhttps://github.com/fastapi/fastapi",
    ),
    _license(
        "Uvicorn",
        "BSD-3-Clause",
        "ASGI サーバーとして使用しています。\nhttps://github.com/encode/uvicorn",
    ),
    _license(
        "Pydantic",
        "MIT",
        "API のスキーマ定義と入力の検証に使用しています。\nhttps://github.com/pydantic/pydantic",
    ),
    _license(
        "NumPy",
        "BSD-3-Clause",
        "音声波形の処理に使用しています。\nhttps://github.com/numpy/numpy",
    ),
    _license(
        "Pillow",
        "MIT-CMU",
        "話者アイコンの読み込みと変換に使用しています。\nhttps://github.com/python-pillow/Pillow",
    ),
    _license(
        "PyYAML",
        "MIT",
        "モデルの設定ファイルの読み込みに使用しています。\nhttps://github.com/yaml/pyyaml",
    ),
    _license(
        "PEFT",
        "Apache-2.0",
        "LoRA を適用したチェックポイントの読み込みに使用しています。"
        "\nhttps://github.com/huggingface/peft",
    ),
    _license(
        "libsndfile / PySoundFile",
        "LGPL-2.1 / BSD-3-Clause",
        "音声ファイルの読み書きに使用しています。\nhttps://github.com/bastibe/python-soundfile",
    ),
]


# エディタは「IRODORI-VOICE Engine / アップデート情報」として表示する。
# エディタ側の updateInfos.json がソフト全体の履歴、こちらはエンジンの履歴を担当する。
ENGINE_UPDATE_INFOS: list[dict[str, Any]] = [
    {
        "version": "0.24.1",
        "descriptions": [
            "VOICEVOX ENGINE 互換の 26 エンドポイントを提供します",
            "複数の合成バックエンドを、1 つの話者一覧へまとめます",
            "モーラ単位の音高・長さの調整に対応しないことを engine_manifest で申告します",
            "長い行を句読点で区間へ割り、同じ声のまま 1 本の音声として返します",
            "ユーザー辞書へ登録した語を OpenJTalk の解析へ反映します",
            "参照音声の latent と合成結果をキャッシュし、同じ要求へ即座に応答します",
            "感嘆詞だけが並ぶ行で落ちる低域を、合成後に不足分だけ補正します",
            "管理画面を /admin で配信します",
        ],
        "contributors": [],
    }
]


_MODEL_VOICE_PREFIX = "aivm:"

_POLICY_UNKNOWN_LICENSE = """\
この声を出している音声モデルには、ライセンスが記載されていません。**配布元が示す条件を
確認したうえでお使いください。** 記載が無いことは、自由に使えることを意味しません。
"""

_POLICY_IRODORI_REFERENCE = """\
この話者の声は、登録された参照音声を手本にして Irodori-TTS が生成したものです。

**参照音声の出どころが定める条件に従ってください。** 音声モデルの声を手本にした場合は
そのモデルの規約が、実在する人物の声を手本にした場合はその人の許諾が必要です。
このエンジンは参照音声の出どころを記録しないため、判断は登録した方に委ねられます。
"""

_POLICY_IRODORI_SEED = """\
この話者の声は、シード値から Irodori-TTS が生成したものです。特定の人物や音声モデルに
由来しないため、[Irodori-TTS](https://github.com/Aratako/Irodori-TTS) のライセンス（MIT）の
範囲でお使いいただけます。

合成した音声には SilentCipher による電子透かしが付与されます。聴感には影響しません。
"""


def speaker_policy(
    backend_id: str | None,
    voice_id: str | None,
    has_reference: bool,
) -> str:
    """「音声ライブラリの利用規約」へ出す、話者ごとの文面。

    エディタはこのページを話者ごとに開く。声の出どころによって守るべき条件が違うため、
    一律の文言ではなく、その話者に当てはまるものだけを返す。取り込んだモデルの声は
    配布元が条件を決めるので、マニフェストに書かれたライセンスをそのまま載せる。
    """

    if backend_id == "aivm" and voice_id:
        return _model_policy(voice_id)
    if backend_id == "irodori":
        return _POLICY_IRODORI_REFERENCE if has_reference else _POLICY_IRODORI_SEED
    # 話者一覧には出ているがレジストリから引けない状態。声の出どころが分からないので、
    # 断定せずに配布元の確認を促す。
    return _POLICY_UNKNOWN_LICENSE


def _model_policy(voice_id: str) -> str:
    from ..backends.sbv2 import metadata

    model_uuid = ""
    if voice_id.startswith(_MODEL_VOICE_PREFIX):
        body = voice_id[len(_MODEL_VOICE_PREFIX) :]
        model_uuid, _, _ = body.rpartition(":")

    model = None
    for candidate in metadata.list_installed():
        if candidate.uuid == model_uuid:
            model = candidate
            break

    if model is None:
        return _POLICY_UNKNOWN_LICENSE

    lines = [f"# {model.name}", ""]
    if model.creators:
        lines.append("制作: " + " / ".join(model.creators))
        lines.append("")

    license_text = (model.license or "").strip()
    if license_text:
        lines.append(license_text)
    else:
        lines.append(_POLICY_UNKNOWN_LICENSE.rstrip())

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "この声は取り込んだ音声モデルによるものです。利用条件を定めるのはモデルの配布元であり、"
        "IRODORI-VOICE ではありません。"
    )
    return "\n".join(lines)
