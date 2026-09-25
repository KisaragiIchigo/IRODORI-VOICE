"""本文の長さから決める尺の上限を検証する。

期待値は実測に対応する。借りた声・同梱話者は切らず、シードの声の外れ値は抑える。
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, paths, duration_cap
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-duration-cap-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice import paths
    from irodori_voice.backends.irodori import duration_cap
    paths.user_data_root.cache_clear()


def tearDownModule():
    paths.user_data_root.cache_clear()
    environment.stop()
    data_dir.cleanup()


class MoraCountTests(unittest.TestCase):
    def test_counts_morae_of_japanese_text(self):
        for text, expected in (
            ("はい。", 2),
            ("わかりました。", 6),
            ("「呼ばれていたよ。", 7),
            ("今日はいい天気ですね。", 11),
        ):
            with self.subTest(text=text):
                self.assertEqual(duration_cap.count_morae(text), expected)

    def test_small_kana_do_not_count_but_long_and_geminate_do(self):
        # 拗音は直前の仮名と合わせて 1 モーラ、長音・促音・撥音はそれぞれ 1 モーラ。
        self.assertEqual(duration_cap.count_morae("きょう"), 2)
        self.assertEqual(duration_cap.count_morae("とっきゅう"), 4)
        self.assertEqual(duration_cap.count_morae("ラーメン"), 4)

    def test_annotation_emoji_is_not_read_as_a_mora(self):
        self.assertEqual(duration_cap.count_morae("🐢はい。"), 2)

    def test_returns_none_without_openjtalk(self):
        with patch.object(duration_cap, "analyze", return_value=None):
            self.assertIsNone(duration_cap.count_morae("はい。"))


class MaxSecondsTests(unittest.TestCase):
    def cap(self, morae, duration_scale=1.0, annotated=False, trusted=True, text="_"):
        with patch.object(duration_cap, "count_morae", return_value=morae):
            with patch.object(
                duration_cap, "count_annotation_emojis", return_value=1 if annotated else 0
            ):
                return duration_cap.resolve_max_seconds(
                    text, duration_scale=duration_scale, trust_prediction=trusted
                )

    def test_borrowed_voices_are_never_cut(self):
        # 実測の最大値。借りた声 3 人・話速 0.5 のいずれも上限を下回る。2 モーラは「はい？」の 1.13。
        # 以前の同梱話者（ナレーション）の 1.32 は、その話者を配らなくなったため外した。
        for morae, seconds in ((2, 1.13), (6, 1.48), (7, 1.72), (11, 2.40), (32, 5.64), (55, 8.92)):
            with self.subTest(morae=morae):
                self.assertGreater(self.cap(morae), seconds)
        self.assertGreater(self.cap(7, duration_scale=2.0), 3.16)

    def test_seed_voices_are_capped_on_short_text(self):
        # 実測の最小値。シードの声の外れ値は、いちばん軽いものでも上限に当たる。
        for morae, seconds in ((2, 3.36), (6, 3.16), (7, 2.72), (11, 3.48)):
            with self.subTest(morae=morae):
                self.assertLess(self.cap(morae), seconds)

    def test_long_text_is_left_alone(self):
        # 長い本文では話者によらず予測が揃うため、誰も上限に当ててはいけない。
        for morae, seconds in ((32, 5.64), (55, 8.92)):
            with self.subTest(morae=morae):
                self.assertGreater(self.cap(morae), seconds)

    def test_annotated_text_keeps_room_for_the_instruction(self):
        # 7 モーラの実測: 借りた声は 🐢 1.60・⏩ 2.48・😆 1.68・📖 1.52 で、どれも通す。
        for seconds in (1.60, 2.48, 1.68, 1.52):
            self.assertGreater(self.cap(7, annotated=True), seconds)
        # 同じ条件のシードの声は ⏩ 6.44・4.32、📖 3.28 で、いずれも抑える。
        for seconds in (6.44, 4.32, 3.28):
            self.assertLess(self.cap(7, annotated=True), seconds)

    def test_annotated_text_gets_more_room_than_plain_text(self):
        self.assertGreater(self.cap(7, annotated=True), self.cap(7))

    def test_floor_protects_very_short_text(self):
        self.assertEqual(self.cap(1), duration_cap.MIN_CAP_SECONDS)
        self.assertEqual(self.cap(2), duration_cap.MIN_CAP_SECONDS)
        self.assertEqual(self.cap(1, annotated=True), duration_cap.ANNOTATED_MIN_CAP_SECONDS)

    def test_short_lines_of_borrowed_voices_are_not_cut(self):
        # 借りた声 3 人の最長: 「そうなの？」（4 モーラ）1.45、「……ふぅ。」（1 モーラ）1.31、
        # 「😮‍💨……ふぅ。」1.37。疑問や三点リーダで伸びた分も通す。
        self.assertGreater(self.cap(4), 1.45)
        self.assertGreater(self.cap(1, text="……ふぅ。"), 1.31)
        self.assertGreater(self.cap(1, annotated=True), 1.37)

    def test_pause_marks_count_once_per_run(self):
        with patch.object(duration_cap, "count_morae", return_value=20):
            with patch.object(duration_cap, "count_annotation_emojis", return_value=0):
                plain = duration_cap.resolve_max_seconds("_", duration_scale=1.0)
                one = duration_cap.resolve_max_seconds("……ふぅ", duration_scale=1.0)
                two = duration_cap.resolve_max_seconds("あ…い...う", duration_scale=1.0)
        self.assertAlmostEqual(one - plain, duration_cap.PAUSE_SECONDS * duration_cap.MARGIN)
        self.assertAlmostEqual(two - plain, 2 * duration_cap.PAUSE_SECONDS * duration_cap.MARGIN)

    def test_untrusted_voices_are_capped_at_the_natural_length(self):
        # 利用者の聴取（シードの声 3 人）。「はい。」は 0.90 秒で正しく 1.50 秒で埋め草、「うん。」は
        # 1.20 秒で「えんちにー」「おーい」、「……ふぅ。」は 1.44 秒で「いーーー」、
        # 「😮‍💨……ふぅ。」は 1.8 秒で「ふううう」。「お疲れさまです。」は 1.60 秒で正しく読めた。
        self.assertLess(self.cap(2, trusted=False), 1.20)
        self.assertLess(self.cap(1, text="……ふぅ。", trusted=False), 1.44)
        self.assertLess(self.cap(1, text="……ふぅ。", annotated=True, trusted=False), 1.80)
        self.assertGreaterEqual(self.cap(8, trusted=False), 1.60)
        # 見積もりそのものが上限。注釈がある行だけ、ため息や間の分を残す。
        estimate = duration_cap.BASE_SECONDS + duration_cap.SECONDS_PER_MORA * 7
        self.assertAlmostEqual(self.cap(7, trusted=False), estimate)
        self.assertGreater(self.cap(7, annotated=True, trusted=False), self.cap(7, trusted=False))

    def test_untrusted_voices_keep_their_long_lines(self):
        # シードの声でも長い本文の予測は借りた声と揃う（32 モーラ 5.04〜5.44、55 モーラ 8.24〜8.80）。
        self.assertGreaterEqual(self.cap(32, trusted=False), 5.44)
        self.assertGreater(self.cap(55, trusted=False), 8.80)

    def test_untrusted_cap_follows_the_speed(self):
        self.assertAlmostEqual(self.cap(11, duration_scale=2.0, trusted=False), self.cap(11, trusted=False) * 2.0)

    def test_scale_moves_the_cap_with_the_prediction(self):
        base = self.cap(11)
        self.assertAlmostEqual(self.cap(11, duration_scale=2.0), base * 2.0)
        self.assertAlmostEqual(self.cap(11, duration_scale=0.5), base * 0.5)

    def test_never_loosens_the_engine_default(self):
        self.assertEqual(self.cap(400), duration_cap.ABSOLUTE_MAX_SECONDS)
        self.assertEqual(self.cap(55, duration_scale=8.0), duration_cap.ABSOLUTE_MAX_SECONDS)

    def test_unknown_reading_leaves_the_default_untouched(self):
        for value in (None, 0):
            with self.subTest(value=value):
                self.assertIsNone(self.cap(value))


if __name__ == "__main__":
    unittest.main()
