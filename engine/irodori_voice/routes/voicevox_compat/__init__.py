"""VOICEVOX ENGINE 互換 API。

ゆっくりMovieMaker や AviUtl プラグインなど、VOICEVOX 対応を謳う外部ツールから
そのまま叩けるようにするための層。エンドポイントの形とフィールド名を本家に合わせる。

対応の程度を正直に書いておく。

  - ``/audio_query`` は OpenJTalk でアクセント句を組み立てて返す。本家と同じ手順。
  - アクセントやモーラ長を編集しても Irodori-TTS の音には反映されない。
    このモデルはテキストから直接 latent を生成し、モーラ単位の制御機構を持たない。
    Style-Bert-VITS2 も同様にモーラ長の直接指定は受けない。
  - speedScale / volumeScale / prePhonemeLength / postPhonemeLength は反映される。
    pitchScale と intonationScale は、対応する話者でのみ効く。

つまり「読み上げさせる」用途では本家と同じように使え、「アクセントを細かく直す」
用途には応えられない。外部ツールの多くは前者しか使わないため、実用上は繋がる。
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    engine_info,
    query,
    speakers,
    synthesis,
    unsupported,
    user_dict,
    word_splits,
)

router = APIRouter(tags=["voicevox-compat"])

# 読む順が使う順と揃うように、名乗りから合成までの流れで並べる。
router.include_router(engine_info.router)
router.include_router(speakers.router)
router.include_router(word_splits.router)
router.include_router(query.router)
router.include_router(synthesis.router)
router.include_router(user_dict.router)
router.include_router(unsupported.router)

__all__ = ["router"]
