"""長いテキストを合成に適した長さへ分割する。

Irodori-TTS は 1 回の合成で最大 30 秒までしか出力できない。さらに実測では
1 行 30〜40 文字のときに最も効率が良く（合成時間が音声長を下回る）、
それより長いとデコードと透かしの処理が伸びて待ち時間が増える。

そこで句読点を優先して区切り、目標文字数に収まる塊へまとめる。
区切り位置は「文として自然な場所」を優先し、どうしても長い文は読点で割る。

鉤括弧で囲まれた範囲は、地の文と混ぜずにひと塊で切り出す。区間は別々に合成して
から繋ぐため、読み方が切り替わるのは区間の境目だけになる。セリフと地の文が同じ
区間に入れば両方が同じ調子で読まれ、逆に囲みの中を句点で割ればひと続きのセリフ
の途中で調子が変わる。囲みの境目だけで切ることで、朗読のように地の文とセリフの
間でだけ読み方が変わる。

ただし囲みだけで上限を超える場合は、30 秒の制限が優先で中でも割る。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 実測で最も効率が良かった長さ。これを目安に塊をまとめる。
DEFAULT_TARGET_CHARS = 38

# これ以上長い塊は、読点しか無くても分割する。30 秒の上限に当たるのを避けるため。
DEFAULT_MAX_CHARS = 60

# 独立した塊として扱うには短すぎる長さ。直前の塊へ繋げる。
#
# 音質を理由にこれを引き上げてはいけない。文として完結していれば、短い区間でも
# 大きくは崩れない（実測で 17 文字の一文が 6kHz 以上 5.54%、44 文字が 10.07%）。
# むしろ両者を繋いで 61 文字にすると 7.06% まで落ち、長さで重み付けした平均 8.8% を
# 下回った。崩れるのは短さではなく「文の途中で切れていること」による。
MIN_CHARS = 6

# 短い断片を前へ繋ぐときに許す長さ。断片を作るよりは繋ぐが、上限は設ける。
ABSORB_LIMIT_RATIO = 1.5

# 単独の区間として生成させるには短すぎる長さ。上限に収まる限り隣へ繋げる。
#
# モデルは短い本文で読み上げる長さを大きく外し、余った尺を埋めるために冒頭へ雑音を置く。
# 純正の Irodori-TTS は文を割らないためこの領域へ入らず、区間へ割るこちらだけが踏む。
#
# 実測（シードから焼いた話者・同じ言い回しで長さだけ変える。値は最初のサンプル）:
#
#      9 文字   -4121   再生した瞬間に雑音が入る
#     14 文字      -1
#     18 文字      -1
#     21 文字      -1
#     26 文字      -1
#
# 14 文字で収まったので、余裕を見て 16 文字を境目にする。繋ぐと上限を超える場合は短いまま
# 残す。単独で短い行（「はい。」など）は繋ぐ相手がいないため、ここでは救えない。
#
# MIN_CHARS とは別に置く。あちらは「固定費だけ消費して効率が悪い」断片の話で、音が壊れる
# かどうかとは基準が違う。あちらを引き上げてはいけないという但し書きは、61 文字へ繋いだ
# 実測（上限 60 を超えている）を根拠にしており、上限内で繋ぐこちらとは別の話。
MIN_SEGMENT_CHARS = 16

# 文の終わりとみなす記号。句点と感嘆・疑問符、閉じ括弧の直後も含む。
_SENTENCE_END = re.compile(r"(?<=[。！？!?])(?=.)|(?<=[。！？!?][」』）\)])(?=.)")

# 文が長すぎるときに使う二次的な区切り。読点と中黒、全角スペース。
_CLAUSE_BREAK = re.compile(r"(?<=[、，,])(?=.)")

# 囲みとして扱う括弧。境目で区間を分け、中では割らない。
_QUOTE_PAIRS = {"「": "」", "『": "』"}

# 閉じ括弧のすぐ後ろに続くとき、囲みの側へ付ける記号。
# 「セリフ」。を割ると句点だけが次の区間の先頭に残り、間の取り方がおかしくなる。
_QUOTE_TAIL_MARKS = "。！？!?、，,"


@dataclass(frozen=True)
class TextSegment:
    """分割後の 1 区間。"""

    index: int
    text: str
    # この区間の後ろに置く無音の長さ。文末なら長め、読点なら短め。
    trailing_silence: float


@dataclass(frozen=True)
class _Piece:
    """分割の途中経過。囲みから来た塊は、割り方と後ろの無音が変わる。"""

    text: str
    from_quote: bool


def _detect_quoted_spans(text: str) -> list[tuple[int, int]]:
    """一番外側の囲みの範囲を (開き括弧の位置, 閉じ括弧の位置) で返す。

    閉じ括弧が現れないまま終わった開き括弧は囲みとして扱わない。閉じ忘れや
    会話の書き出しだけを渡されたときに、全体が 1 区間へ固まって 30 秒の上限に
    当たるのを避けるため。入れ子（「彼は『行く。』と言った。」）は外側だけを返す。
    """

    spans: list[tuple[int, int]] = []
    opened: list[tuple[str, int]] = []

    for index, char in enumerate(text):
        close_char = _QUOTE_PAIRS.get(char)
        if close_char is not None:
            opened.append((close_char, index))
            continue
        if opened and char == opened[-1][0]:
            _, start = opened.pop()
            if not opened:
                spans.append((start, index))

    return spans


def _split_into_pieces(text: str) -> list[_Piece]:
    """囲みと地の文へ分ける。閉じ括弧の直後の句読点は囲みの側へ付ける。"""

    pieces: list[_Piece] = []
    previous = 0

    for start, end in _detect_quoted_spans(text):
        if previous < start:
            pieces.append(_Piece(text=text[previous:start], from_quote=False))
        stop = end + 1
        while stop < len(text) and text[stop] in _QUOTE_TAIL_MARKS:
            stop += 1
        pieces.append(_Piece(text=text[start:stop], from_quote=True))
        previous = stop

    if previous < len(text):
        pieces.append(_Piece(text=text[previous:], from_quote=False))

    return [piece for piece in pieces if piece.text.strip() != ""]


def _split_by(pattern: re.Pattern[str], text: str) -> list[str]:
    return [part for part in pattern.split(text) if part.strip() != ""]


def _merge_into_chunks(
    parts: list[str], *, target: int, maximum: int, absorb_limit: int
) -> list[str]:
    """細かく割れた断片を、目標文字数に近い塊へまとめ直す。"""

    chunks: list[str] = []
    buffer = ""

    for part in parts:
        # 単体で上限を超える断片は、囲みの中まで含めて割り直す。
        if len(part) > maximum:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            pieces = _split_by(_SENTENCE_END, part)
            if len(pieces) == 1:
                pieces = _split_by(_CLAUSE_BREAK, part)
            if len(pieces) > 1:
                chunks.extend(
                    _merge_into_chunks(
                        pieces, target=target, maximum=maximum, absorb_limit=absorb_limit
                    )
                )
            else:
                # 区切る手がかりが無い。上限で機械的に切る。
                chunks.extend(part[i : i + maximum] for i in range(0, len(part), maximum))
            continue

        if buffer == "":
            buffer = part
        elif len(buffer) + len(part) <= target:
            buffer += part
        elif len(part) < MIN_CHARS and len(buffer) + len(part) <= absorb_limit:
            # 「はい。」のような断片は、単体だと固定費だけ消費して効率が悪い。
            buffer += part
        else:
            chunks.append(buffer)
            buffer = part

    if buffer:
        chunks.append(buffer)
    return chunks


def _absorb_short_tail(chunks: list[str], *, absorb_limit: int) -> list[str]:
    """短すぎる塊を隣へ繋げる。

    「はい。」だけで 1 区間にすると固定費（約 3 秒）だけ消費するうえ、短い区間は
    そこだけ音が崩れる。繋げると長くなりすぎる場合だけ、独立したまま残す。
    """

    if len(chunks) <= 1:
        return chunks

    merged: list[str] = []
    for chunk in chunks:
        if merged and len(chunk) < MIN_CHARS and len(merged[-1]) + len(chunk) <= absorb_limit:
            merged[-1] += chunk
        else:
            merged.append(chunk)
    return merged


def _absorb_short_segments(chunks: list[str], *, maximum: int) -> list[str]:
    """単独では短すぎる塊を、上限に収まる限り隣へ繋げる。

    先頭の塊だけは後ろへ寄せる（前が無いため）。それ以外は前へ繋ぐので、読み上げの
    順序も区切りの位置も変わらない。繋ぐと上限を超える場合は短いまま残す。
    """

    if len(chunks) <= 1:
        return chunks

    merged = list(chunks)
    while (
        len(merged) > 1
        and len(merged[0]) < MIN_SEGMENT_CHARS
        and len(merged[0]) + len(merged[1]) <= maximum
    ):
        merged[1] = merged[0] + merged[1]
        del merged[0]

    absorbed: list[str] = []
    for chunk in merged:
        if (
            absorbed
            and len(chunk) < MIN_SEGMENT_CHARS
            and len(absorbed[-1]) + len(chunk) <= maximum
        ):
            absorbed[-1] += chunk
        else:
            absorbed.append(chunk)
    return absorbed


def _chunks_from_piece(
    piece: _Piece, *, target: int, maximum: int, absorb_limit: int
) -> list[_Piece]:
    """1 つの塊を、目標文字数に収まる区間候補へ割る。"""

    if piece.from_quote:
        # セリフはひと続きで読ませる。上限を超えるときだけ、中でも割る。
        texts = (
            [piece.text]
            if len(piece.text) <= maximum
            else _absorb_short_segments(
                _merge_into_chunks(
                    [piece.text], target=target, maximum=maximum, absorb_limit=absorb_limit
                ),
                maximum=maximum,
            )
        )
    else:
        texts = _absorb_short_segments(
            _absorb_short_tail(
                _merge_into_chunks(
                    _split_by(_SENTENCE_END, piece.text),
                    target=target,
                    maximum=maximum,
                    absorb_limit=absorb_limit,
                ),
                absorb_limit=absorb_limit,
            ),
            maximum=maximum,
        )

    return [_Piece(text=text, from_quote=piece.from_quote) for text in texts]


def _trailing_silence(
    chunk: _Piece, *, is_last: bool, sentence_silence: float, clause_silence: float
) -> float:
    """区間の後ろに置く無音を決める。"""

    if is_last:
        return 0.0
    # 「……」と彼女は言った、の形は朗読では間を置かずに続く。セリフが複数区間へ
    # 割れた場合も、ひと続きの発話なので間は詰めておく。
    if chunk.from_quote:
        return clause_silence
    if chunk.text.rstrip().endswith(("。", "！", "？", "!", "?", "」", "』", "）", ")")):
        return sentence_silence
    return clause_silence


def split_text_into_segments(
    text: str,
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
    sentence_silence: float = 0.25,
    clause_silence: float = 0.1,
    split_at_quotes: bool = True,
) -> list[TextSegment]:
    """テキストを合成単位へ分割する。

    囲みが無く上限にも収まるなら、そのまま 1 区間で返す。区間の後ろに置く無音は、
    文末で区切った場合は長め、読点とセリフの直後は短めにして間を自然にする。
    """

    stripped = text.strip()
    if stripped == "":
        return []

    pieces = (
        _split_into_pieces(stripped)
        if split_at_quotes
        else [_Piece(text=stripped, from_quote=False)]
    )

    if len(pieces) == 1 and not pieces[0].from_quote and len(stripped) <= max_chars:
        return [TextSegment(index=0, text=stripped, trailing_silence=0.0)]

    absorb_limit = int(max_chars * ABSORB_LIMIT_RATIO)
    chunks = [
        chunk
        for piece in pieces
        for chunk in _chunks_from_piece(
            piece, target=target_chars, maximum=max_chars, absorb_limit=absorb_limit
        )
    ]

    return [
        TextSegment(
            index=index,
            text=chunk.text.strip(),
            trailing_silence=_trailing_silence(
                chunk,
                is_last=index == len(chunks) - 1,
                sentence_silence=sentence_silence,
                clause_silence=clause_silence,
            ),
        )
        for index, chunk in enumerate(chunks)
    ]
