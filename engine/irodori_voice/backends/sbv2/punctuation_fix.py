"""pyopenjtalk が返す記号の読みを、Style-Bert-VITS2 が扱える半角へそろえる。

SBV2 は、pyopenjtalk から返った読みが全角「？」のときだけ半角へ戻す分岐を持つ
（nlp/japanese/g2p.py の text_to_sep_kata）。「！」に同じ分岐は無い。一方
pyopenjtalk-plus 0.4.1 は「!」「?」のどちらの読みも全角で返すため、感嘆符を
含む行は素通りして後段で落ちる。

    text_to_sep_kata("こんにちは!")
        -> (["こんにちは", "!"], ["コンニチワ", "！"])
                                             ^^ 半角へ戻らない
    -> __kata_to_phoneme_list("！")
        -> ValueError: Input must be katakana only: ！

「こんにちは！」のような普通の文でも起きるため、モデルの話者は感嘆符を書いた時点で
合成できなくなる。エディタが使う /audio_query → /synthesis の経路でも同じ。

SBV2 本体には手を入れず、返り値を通過させる層でそろえる。上流の更新をそのまま
取り込めるようにするため。
"""

from __future__ import annotations

# SBV2 の PUNCTUATIONS は半角のみを持つ。pyopenjtalk が全角で返す読みをここで戻す。
# 「？」は SBV2 側にも分岐があるため二重になるが、どちらが先に直しても結果は同じで、
# 上流が分岐を消しても壊れない。
_FULLWIDTH_TO_HALFWIDTH = {"！": "!", "？": "?"}


def apply_punctuation_fix() -> None:
    """text_to_sep_kata の読み側を半角へそろえる。二度目以降は何もしない。"""

    from style_bert_vits2.nlp.japanese import g2p as sbv2_g2p

    original = sbv2_g2p.text_to_sep_kata
    if getattr(original, "_irodori_punctuation_fixed", False):
        return

    def text_to_sep_kata(
        norm_text: str, raise_yomi_error: bool = False
    ) -> tuple[list[str], list[str]]:
        sep_text, sep_kata = original(norm_text, raise_yomi_error=raise_yomi_error)
        return sep_text, [_FULLWIDTH_TO_HALFWIDTH.get(kata, kata) for kata in sep_kata]

    text_to_sep_kata._irodori_punctuation_fixed = True  # type: ignore[attr-defined]
    sbv2_g2p.text_to_sep_kata = text_to_sep_kata
