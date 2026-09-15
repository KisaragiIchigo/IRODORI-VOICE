"""合成に使うシードを決める。

参照音声を持たない話者（キャプションのみ）では、シードが声そのものを決める。
つまりシードが揺れると同じ話者でも別人になる。

VOICEVOX 互換 API には「この行の声」を指定する手段が無いため、エンジン側で
話者ごとに安定したシードを割り当てる必要がある。テキストから導出してはならない
（行ごとに別人になる）。プロセスごとに変わる ``hash()`` も使ってはならない
（再起動で声が変わる）。

そのため話者の識別子から ``hashlib`` で決定的に導出する。同じ話者なら、
どの行でも、何度再起動しても同じ声になる。
"""

from __future__ import annotations

import hashlib

MAX_SEED = 2**31 - 1


def resolve_voice_seed(voice_id: str, *, style_id: str | None = None) -> int:
    """話者（とスタイル）から安定したシードを導出する。

    スタイルもキーに含めるのは、スタイル違いでわずかに声色が変わるのを
    許容するため。同一スタイル内では常に同じ声になる。
    """

    key = f"{voice_id}::{style_id or ''}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % MAX_SEED


def resolve_seed_for_request(
    *,
    voice_id: str,
    style_id: str | None,
    explicit_seed: int | None,
) -> int:
    """要求で指定があればそれを、無ければ話者固定のシードを返す。

    独自 API は行ごとのシードを持つためそちらを尊重する。
    互換 API は指定を持たないので、話者固定のシードに落ちる。
    """

    if explicit_seed is not None:
        return int(explicit_seed) % MAX_SEED
    return resolve_voice_seed(voice_id, style_id=style_id)
