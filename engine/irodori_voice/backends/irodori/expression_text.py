"""注釈を含む文の末尾を、合成専用の本文で補う。"""

import re

from ...vendor.irodori_tts.duration import ALLOWED_ANNOTATION_EMOJIS

_ANNOTATION = re.compile("|".join(sorted(map(re.escape, ALLOWED_ANNOTATION_EMOJIS), key=len, reverse=True)))
_SENTENCE = re.compile(r"[^。！？!?\n]+[。！？!?]*")


def append_expression_pause(text: str) -> str:
    def append(match: re.Match[str]) -> str:
        sentence = match.group()
        tail = sentence.rstrip()
        ending = tail.rstrip("。！？!?」』）)\"'")
        if not _ANNOTATION.search(sentence) or ending.endswith(("…", "..")):
            return sentence
        position = len(tail.rstrip("。！？!?」』）)\"'"))
        return sentence[:position] + ".." + sentence[position:]

    return _SENTENCE.sub(append, text)
