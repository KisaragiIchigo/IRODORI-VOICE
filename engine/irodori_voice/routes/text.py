"""読み上げ前のテキスト整形。

エンジンは長い行を内部で区間へ割ってから合成するが、その結果はエディタの行には
反映されない。エディタ側で行を分けておきたい場合に、同じ規則で割った結果を返す。

文の途中で切れた断片は音が崩れる（実測で 8 文字の断片は 6kHz 以上のエネルギーが
0.26%）。一方、文として完結していれば 17 文字でも 5.54% は保つ。長さだけでは
判別できないが、極端に短い行は途中で切れている可能性が高いので目印として返す。
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import TextSplitOut, TextSplitRequest, TextSplitSegmentOut
from ..state import EngineState
from ..synthesis.steps.split_text import split_text_into_segments

router = APIRouter(prefix="/text", tags=["text"])


def _state(request: Request) -> EngineState:
    return request.app.state.engine

# これを下回る行は、文の途中で切れている可能性が高い。警告の閾値として使う。
# 完結した一文なら 17 文字でも実用に足りるため、明らかに短いものだけを拾う。
SHORT_LINE_CHARS = 15


@router.post("/split", response_model=TextSplitOut)
def split(request: Request, payload: TextSplitRequest) -> TextSplitOut:
    """長い文章を、合成に向く長さの行へ割る。

    区切りは句点を優先し、収まらない場合だけ読点で割る。鉤括弧で囲まれたセリフは
    地の文と分けてひと塊にする。エンジンが合成時に使う規則と同じものを使うため、
    ここで割った結果はそのまま 1 行 1 合成になる。
    """

    segments = split_text_into_segments(
        payload.text,
        target_chars=payload.target_chars,
        max_chars=payload.max_chars,
        split_at_quotes=_state(request).settings.split_at_quotes,
    )

    lines = [
        TextSplitSegmentOut(
            index=segment.index,
            text=segment.text,
            chars=len(segment.text),
            is_short=len(segment.text) < SHORT_LINE_CHARS,
        )
        for segment in segments
    ]

    return TextSplitOut(
        segments=lines,
        joined="\n".join(line.text for line in lines),
        total_chars=len(payload.text.strip()),
        short_line_count=sum(1 for line in lines if line.is_short),
        short_line_threshold=SHORT_LINE_CHARS,
    )
