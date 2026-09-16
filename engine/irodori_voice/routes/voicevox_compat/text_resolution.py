"""AudioQuery から、合成へ渡すテキストを決める。

アクセント句の組み立てと、そこから元の表記を取り戻す手順。/audio_query と
/synthesis の両方がここを通ることで、往復の食い違いが起きないようにする。"""

from __future__ import annotations

from ...voicevox.accent import accent_phrases_to_text, build_accent_phrases
from ...voicevox.query_memory import phrase_key
from ...voicevox.schemas import AccentPhrase, AudioQuery
from ...voicevox.word_splits import split_by_marker, strip_phrase_markers
from .shared import query_memory


def accent_phrases_for(text: str) -> list[AccentPhrase]:
    """フレーズ分割辞書のマーカーを区切りとして、アクセント句を組み立てる。

    マーカーを含んだまま OpenJTalk へ渡すと記号として読まれ、句の数が変わる。
    ``kana`` からの組み直しと ``/audio_query`` の結果を突き合わせるには、
    どちらも同じ手順で組まなければならない。
    """

    phrases: list[AccentPhrase] = []
    for part in split_by_marker(text):
        phrases.extend(build_accent_phrases(part))
    return phrases


def _text_from_kana(payload: AudioQuery) -> str | None:
    """AudioQuery に添えておいた元の表記を、読みが一致するときだけ採り出す。

    利用者がエディタで読みを直した場合、``kana`` は直す前の表記のまま送られて
    くる。読みを組み直して突き合わせ、一致するときだけ採用する。
    """

    kana = (payload.kana or "").strip()
    if kana == "":
        return None

    rebuilt = accent_phrases_for(kana)
    if not rebuilt or phrase_key(rebuilt) != phrase_key(payload.accent_phrases):
        return None
    return kana


def _source_text_candidate(payload: AudioQuery) -> str:
    """元の表記を、確かな順に探す。"""

    remembered = query_memory.recall(payload.accent_phrases)
    if remembered is not None:
        return remembered

    from_kana = _text_from_kana(payload)
    if from_kana is not None:
        # 次からは組み直しを省けるよう覚えておく。
        query_memory.remember(payload.accent_phrases, from_kana)
        return from_kana

    return accent_phrases_to_text(payload.accent_phrases)


def resolve_source_text(payload: AudioQuery) -> str:
    """合成に使うテキストを決める。

    元の表記が分かればそちらを使う。読みだけで合成すると長音が母音字のまま
    モデルへ渡り（「カード」が「カアド」）、別の語に化ける。

    記憶はプロセス内にしか無く、エンジンの再起動やプロジェクトの開き直しで
    外れる。その穴を ``kana`` に載せた表記が埋める。

    フレーズ分割辞書のマーカーはここで落とす。Irodori-TTS は表記から直接音を
    作るモデルで、マーカーが残っていると区切り記号として読まれ、間を空けない
    はずの分割にポーズが入る。
    """

    return strip_phrase_markers(_source_text_candidate(payload))
