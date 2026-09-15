"""長いテキストを合成に適した長さへ分割する。

Irodori-TTS は 1 回の合成で最大 30 秒までしか出力できない。さらに実測では
1 行 30〜40 文字のときに最も効率が良く（合成時間が音声長を下回る）、
それより長いとデコードと透かしの処理が伸びて待ち時間が増える。

そこで句読点を優先して区切り、目標文字数に収まる塊へまとめる。
区切り位置は「文として自然な場所」を優先し、どうしても長い文は読点で割る。
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

# 文の終わりとみなす記号。句点と感嘆・疑問符、閉じ括弧の直後も含む。
_SENTENCE_END = re.compile(r"(?<=[。！？!?])(?=.)|(?<=[。！？!?][」』）\)])(?=.)")

# 文が長すぎるときに使う二次的な区切り。読点と中黒、全角スペース。
_CLAUSE_BREAK = re.compile(r"(?<=[、，,])(?=.)")


@dataclass(frozen=True)
class TextSegment:
    """分割後の 1 区間。"""

    index: int
    text: str
    # この区間の後ろに置く無音の長さ。文末なら長め、読点なら短め。
    trailing_silence: float


def _split_by(pattern: re.Pattern[str], text: str) -> list[str]:
    return [part for part in pattern.split(text) if part.strip() != ""]


def _merge_into_chunks(
    parts: list[str], *, target: int, maximum: int, absorb_limit: int
) -> list[str]:
    """細かく割れた断片を、目標文字数に近い塊へまとめ直す。"""

    chunks: list[str] = []
    buffer = ""

    for part in parts:
        # 単体で上限を超える断片は、読点でさらに割る。
        if len(part) > maximum:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            clauses = _split_by(_CLAUSE_BREAK, part)
            if len(clauses) > 1:
                chunks.extend(
                    _merge_into_chunks(
                        clauses, target=target, maximum=maximum, absorb_limit=absorb_limit
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


def split_text_into_segments(
    text: str,
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
    sentence_silence: float = 0.25,
    clause_silence: float = 0.1,
) -> list[TextSegment]:
    """テキストを合成単位へ分割する。

    分割が要らない長さならそのまま 1 区間で返す。区間の後ろに置く無音は、
    文末で区切った場合は長め、読点で区切った場合は短めにして間を自然にする。
    """

    stripped = text.strip()
    if stripped == "":
        return []

    if len(stripped) <= max_chars:
        return [TextSegment(index=0, text=stripped, trailing_silence=0.0)]

    absorb_limit = int(max_chars * ABSORB_LIMIT_RATIO)
    sentences = _split_by(_SENTENCE_END, stripped)
    chunks = _absorb_short_tail(
        _merge_into_chunks(
            sentences, target=target_chars, maximum=max_chars, absorb_limit=absorb_limit
        ),
        absorb_limit=absorb_limit,
    )

    segments: list[TextSegment] = []
    for index, chunk in enumerate(chunks):
        is_last = index == len(chunks) - 1
        if is_last:
            silence = 0.0
        elif chunk.rstrip().endswith(("。", "！", "？", "!", "?", "」", "』", "）", ")")):
            silence = sentence_silence
        else:
            silence = clause_silence
        segments.append(
            TextSegment(index=index, text=chunk.strip(), trailing_silence=silence)
        )
    return segments
