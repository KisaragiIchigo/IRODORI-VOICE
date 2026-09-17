"""AudioQuery から、合成へ渡すテキストを決める。

アクセント句の組み立てと、そこから元の表記を取り戻す手順。/audio_query と
/synthesis の両方がここを通ることで、往復の食い違いが起きないようにする。"""

from __future__ import annotations

from ...backends.irodori.reading_overrides import apply_reading_overrides
from ...vendor.irodori_tts.duration import count_annotation_emojis
from ...voicevox.accent import accent_phrases_to_text, build_accent_phrases
from ...voicevox.query_memory import phrase_key
from ...voicevox.schemas import AccentPhrase, AudioQuery
from ...voicevox.user_dict import shared_user_dict
from ...voicevox.word_splits import (
    PHRASE_MARKER,
    apply_word_splits,
    split_by_marker,
    strip_phrase_markers,
)
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

    if PHRASE_MARKER not in kana:
        kana = apply_word_splits(kana)
    rebuilt = accent_phrases_for(kana)
    if phrase_key(rebuilt) != phrase_key(payload.accent_phrases):
        return None
    if not rebuilt and not count_annotation_emojis(kana):
        return None
    return kana


def _source_text_candidate(payload: AudioQuery) -> str:
    """元の表記を、確かな順に探す。"""

    from_kana = _text_from_kana(payload)
    if from_kana is not None:
        return from_kana

    # 読みだけのキーでは、絵文字・句読点・同音異義語の違いを区別できない。
    remembered = query_memory.recall(payload.accent_phrases)
    if remembered is not None:
        return remembered

    return accent_phrases_to_text(payload.accent_phrases)


def resolve_source_text(payload: AudioQuery) -> str:
    """合成に使うテキストを決める。

    元の表記が分かればそちらを使う。読みだけで合成すると長音が母音字のまま
    モデルへ渡り（「カード」が「カアド」）、別の語に化ける。

    行ごとの ``kana`` に載せた表記を優先する。読みを編集して表記と合わなくなった
    場合や、元の表記を返さないクライアントに限り、キャッシュとモーラ列で補う。

    辞書の読みは、フレーズ分割辞書のマーカーが残っているうちに当てる。マーカーを
    先に落とすと表記がつながり、解析が「証券取引所」のような複合語を 1 語として
    切るため、その内側にある登録語（「取引所」）が語の切れ目に一致せず当たらない。
    画面のアクセント句はマーカーで割ってから組み立てるので登録語が当たり、同じ文
    なのに画面は辞書どおり、音は辞書を無視するという食い違いになる。

    マーカーを落とすのは読みを当てたあと。Irodori-TTS は表記から直接音を作る
    モデルで、マーカーが残っていると区切り記号として読まれ、間を空けないはずの
    分割にポーズが入る。
    """

    candidate = _source_text_candidate(payload)
    resolved = apply_reading_overrides(candidate, shared_user_dict().reading_overrides())
    return strip_phrase_markers(resolved)
