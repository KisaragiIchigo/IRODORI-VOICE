"""本文を語へ分け、それぞれが本文のどこを占めて何と読まれるかを OpenJTalk から読む。

使い道は 2 つある。ユーザー辞書の読み替えを当てる位置を決めること（``token_boundaries``）と、
読みの無い記号を落とすこと（``analyze`` の ``pron``）。

語の切れ目が要るのは、語の途中で読み替えを当てると別の語が壊れるため。文字種を見る
だけでは切れ目を言い当てられない。「楽天」は「楽天市場」の中でも読ませたく、「神」は
「神社」の中では読ませたくない——この差は形態素解析にしか分からない。

解析にはユーザー辞書を積んだ状態の OpenJTalk を使うため、切れ目は辞書の優先度に
従う。優先度を最大にした語はそれ自体が 1 語として切り出され（「神」を最大で登録すると
「神社」が「神」と「社」に割れる）、下げれば元の語の切れ目が残る。VOICEVOX の優先度と
同じ考え方で、利用者が優先度スライダーで加減できる。

解析結果は本文の上へそのまま戻せない。OpenJTalk は数字の並びを読みへ変換し
（「21,000」が「二十一，０００」）、空白を落とし、波ダッシュの字を入れ替えるため、
語を並べ直しても元の文字列にはならない。そこで語を本文の上へ 1 つずつ照合し、
対応が取れない範囲は読みが分からない区間として残す。返す区間は本文を隙間なく覆う。
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 解析結果と本文がずれたときに、次の語を本文上で探す範囲（文字数）。読みへ変換された
# 数字がこの幅を超えることは稀で、広く取りすぎると遠くの同じ語へ飛びついて対応が狂う。
_RESYNC_WINDOW = 8


@dataclass(frozen=True)
class TokenSpan:
    """本文の一区間と、その読み。

    ``pron`` が ``None`` の区間は、解析結果と対応が取れなかった範囲。読みが無いのでは
    なく、分からない。
    """

    start: int
    end: int
    pron: str | None


def _features(text: str) -> list[tuple[str, str]] | None:
    """本文を語へ分け、表記と読みの組で返す。OpenJTalk が使えなければ ``None``。"""

    try:
        import pyopenjtalk
    except ImportError:
        return None

    try:
        return [
            (feature["string"], feature["pron"])
            for feature in pyopenjtalk.run_frontend(text)
        ]
    except Exception:
        # 解析に失敗しても合成は続けられる。分からないものとして扱うが、握りつぶすと
        # 「辞書が効かない」「記号が読まれる」の原因が追えなくなるため記録は残す。
        logger.exception("本文の解析に失敗しました")
        return None


def analyze(text: str) -> list[TokenSpan] | None:
    """NFKC 済みの本文を、語の区間へ分ける。

    返す区間は ``text`` を先頭から末尾まで隙間なく覆う。OpenJTalk が無いときは ``None``。
    """

    features = _features(text)
    if features is None:
        return None

    spans: list[TokenSpan] = []
    position = 0
    index = 0
    while index < len(features) and position < len(text):
        surface, pron = features[index]
        token = unicodedata.normalize("NFKC", surface)

        if token and text.startswith(token, position):
            spans.append(TokenSpan(position, position + len(token), pron))
            position += len(token)
            index += 1
            continue

        if text[position].isspace():
            # 空白は解析結果に現れない。語の切れ目として読み飛ばす。
            spans.append(TokenSpan(position, position + 1, None))
            position += 1
            continue

        found = text.find(token, position, position + _RESYNC_WINDOW) if token else -1
        if found >= 0:
            # 間に解析結果と対応しない文字がある。読点や記号の字が入れ替わった範囲で、
            # 中の読みは分からない。1 つの区間として残して先へ進む。
            spans.append(TokenSpan(position, found, None))
            position = found
            continue

        # 本文の上に見当たらない語。読みへ変換された数字がこれにあたる。語ごと飛ばし、
        # 次の語で本文との対応を取り直す。
        index += 1

    if position < len(text):
        spans.append(TokenSpan(position, len(text), None))
    return spans


def token_boundaries(text: str) -> frozenset[int] | None:
    """NFKC 済みの本文について、語の切れ目になる文字位置を返す。

    OpenJTalk が無いときは ``None`` を返す。呼び出し側は切れ目が分からないものとして
    扱う。位置は文字数で数え、``0`` と文末は常に切れ目に含める。
    """

    spans = analyze(text)
    if spans is None:
        return None

    bounds = {0, len(text)}
    for span in spans:
        bounds.add(span.start)
        bounds.add(span.end)
    return frozenset(bounds)
