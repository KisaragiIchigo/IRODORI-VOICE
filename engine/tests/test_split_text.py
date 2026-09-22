"""合成単位への分割の回帰確認。

区間は別々に合成して繋ぐため、区間の切れ目がそのまま読み方の切れ目になる。
セリフと地の文が分かれること、セリフの中では切れないこと、上限を超える場合は
30 秒の制限が優先されることを確かめる。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from irodori_voice.synthesis.steps.split_text import (
    DEFAULT_MAX_CHARS,
    MIN_SEGMENT_CHARS,
    _absorb_short_segments,
    split_text_into_segments,
)

# 2 文で目標文字数を超えるセリフ。囲みの有無で分割が変わることを見るために使う。
SPEECH = "今日はとてもいい天気で気持ちがいいですね。せっかくだから外の公園まで散歩に行きましょう。"
QUOTED = "「" + SPEECH + "」"
TAIL = "と彼女は笑って言った。それから二人は歩き出した。"

# 囲みだけで上限を超える本文。閉じ括弧の有無で挙動を見分けるために使う。
LONG_SPEECH = "ここから先は足場がとても悪いので十分に気をつけてください。転んでしまうと大きな怪我につながります。雨の日は特に滑りやすいです。"


def texts(text: str, **kwargs) -> list[str]:
    return [segment.text for segment in split_text_into_segments(text, **kwargs)]


class SplitTextTests(unittest.TestCase):
    def test_囲みが無く上限以下ならそのまま1区間(self):
        text = "今日はいい天気ですね。散歩に行きましょう。"
        self.assertEqual(texts(text), [text])

    def test_セリフと地の文を別の区間にする(self):
        # 上限に収まる短い行でも、混ぜると両方が同じ調子で読まれるため分ける。
        text = "「行こう。」と彼は言った。"

        self.assertLess(len(text), DEFAULT_MAX_CHARS)
        self.assertEqual(texts(text), ["「行こう。」", "と彼は言った。"])

    def test_セリフの中の句点では割らない(self):
        text = QUOTED + TAIL

        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertEqual(texts(text)[0], QUOTED)

    def test_囲みが無ければ同じ本文でも句点で割る(self):
        text = SPEECH + TAIL

        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertEqual(texts(text)[0], "今日はとてもいい天気で気持ちがいいですね。")

    def test_閉じ括弧の直後の句点はセリフ側へ付ける(self):
        quoted = "「ホチキス留めは必ず1枚目の向きと上下を目視で確認。左上へ斜めに留める」。"
        text = quoted + "次の工程へ進みます。確認が済んだら声をかけてください。"

        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertEqual(texts(text)[0], quoted)

    def test_二重鉤括弧の入れ子は外側だけを囲みとして扱う(self):
        text = "「彼は『わかった。行く。』と答えた。だから私は待つことにした。」それから何も起きなかった。静かな夜だった。明日も晴れるといいですね。"

        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertEqual(
            texts(text)[0], "「彼は『わかった。行く。』と答えた。だから私は待つことにした。」"
        )

    def test_閉じ括弧が無い開き括弧は囲みとして扱わない(self):
        text = "「" + LONG_SPEECH

        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertGreater(len(texts(text)), 1)

    def test_囲みが上限を超えるときは中でも割る(self):
        text = "「" + LONG_SPEECH + "」"

        segments = texts(text)
        self.assertGreater(len(text), DEFAULT_MAX_CHARS)
        self.assertGreater(len(segments), 1)
        for segment in segments:
            self.assertLessEqual(len(segment), DEFAULT_MAX_CHARS)

    def test_割った区間を繋ぐと元の文字列に戻る(self):
        text = "彼女は窓の外を見た。" + QUOTED + TAIL

        self.assertEqual("".join(texts(text)), text)

    def test_セリフの直後は間を詰め地の文の句点では間を置く(self):
        segments = split_text_into_segments("彼女は窓の外を見た。" + QUOTED + TAIL)

        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].trailing_silence, 0.25)
        self.assertEqual(segments[1].trailing_silence, 0.1)
        self.assertEqual(segments[2].trailing_silence, 0.0)

    def test_split_at_quotesを切ると囲みを無視して句点で割る(self):
        text = QUOTED + TAIL

        self.assertEqual(
            texts(text, split_at_quotes=False)[0],
            "「今日はとてもいい天気で気持ちがいいですね。",
        )

    def test_短い塊は隣へ繋いで単独では生成させない(self):
        # 短い区間はモデルが読み上げる長さを外し、冒頭へ雑音を置く。
        # 先頭は後ろへ寄せる（前が無いため）。
        self.assertEqual(
            _absorb_short_segments(["あ" * 9, "い" * 46], maximum=60),
            ["あ" * 9 + "い" * 46],
        )
        # 先頭以外は前へ繋ぐので、読み上げの順序も区切りの位置も変わらない。
        self.assertEqual(
            _absorb_short_segments(["あ" * 40, "い" * 10, "う" * 40], maximum=60),
            ["あ" * 40 + "い" * 10, "う" * 40],
        )
        # 繋ぐと上限を超えるなら短いまま残す。切るより短いほうがまし。
        self.assertEqual(
            _absorb_short_segments(["あ" * 9, "い" * 55], maximum=60),
            ["あ" * 9, "い" * 55],
        )
        # 繋ぐ相手がいなければそのまま。単独で短い行はここでは救えない。
        self.assertEqual(_absorb_short_segments(["あ" * 3], maximum=60), ["あ" * 3])

    def test_セリフを割るときも短い先頭区間を作らない(self):
        text = (
            "「呼ばれていたよ。ルグニカ王国の近衛騎士団で、団長であるマーコス団長を除けば"
            "もっとも序列が高いのはユリウスだ。副団長もいるにはいるんだけど、こちらは"
            "名目だけの名誉職扱いだからほぼ空席と思ってもらっていい」"
        )
        segments = texts(text)
        # 以前はここが 9 / 46 / 47 文字に割れ、先頭の 9 文字が単独で生成されていた。
        self.assertEqual(len(segments), 2)
        for segment in segments:
            self.assertGreaterEqual(len(segment), MIN_SEGMENT_CHARS)
            self.assertLessEqual(len(segment), DEFAULT_MAX_CHARS)
        self.assertEqual("".join(segments), text)

    def test_単独の短い行はそのまま1区間(self):
        self.assertEqual(texts("はい。"), ["はい。"])

    def test_空文字列は区間を作らない(self):
        self.assertEqual(split_text_into_segments("   "), [])


if __name__ == "__main__":
    unittest.main()
