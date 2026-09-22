"""フレーズ分割辞書の当たり方の回帰確認。利用者の辞書は一時領域へ隔離する。

読み方＆アクセント辞書からの同時登録は ``単語=_単語_`` の形で入る。この形が本文の上で
狙いどおりに当たること（全角保存された表記が半角の本文へ当たること、マーカーが増えない
こと、合成テキストには残らないこと）を確認する。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, word_splits
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-word-splits-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice.voicevox import word_splits


def tearDownModule():
    environment.stop()
    data_dir.cleanup()


class WordSplitsTests(unittest.TestCase):
    def apply(self, splits, text):
        with patch(
            "irodori_voice.voicevox.word_splits.load_splits", return_value=splits
        ):
            return word_splits.apply_word_splits(text)

    def test_読点はそのまま残り間が空く(self):
        applied = self.apply({"台湾証券取引所": "台湾証券、取引所"}, "台湾証券取引所の値")
        self.assertEqual(applied, "台湾証券、取引所の値")

    def test_アンダースコアはマーカーへ畳まれる(self):
        applied = self.apply({"台湾証券取引所": "台湾証券_取引所"}, "台湾証券取引所の値")
        self.assertEqual(applied, "台湾証券|取引所の値")
        self.assertEqual(word_splits.split_by_marker(applied), ["台湾証券", "取引所の値"])
        self.assertEqual(word_splits.strip_phrase_markers(applied), "台湾証券取引所の値")

    def test_同時登録の形は語を単独の区間へ切り出す(self):
        # 語の前後がマーカーになることで、複合語の内側にある登録語も語の切れ目になる。
        applied = self.apply({"取引所": "_取引所_"}, "台湾証券取引所の値")
        self.assertEqual(applied, "台湾証券|取引所|の値")
        self.assertEqual(
            word_splits.split_by_marker(applied), ["台湾証券", "取引所", "の値"]
        )

    def test_全角で登録した語が半角の本文へ当たる(self):
        applied = self.apply({"ＧＵＩ": "_ＧＵＩ_"}, "GUIの操作")
        self.assertEqual(applied, "|ＧＵＩ|の操作")
        self.assertEqual(word_splits.split_by_marker(applied), ["ＧＵＩ", "の操作"])

    def test_半角で登録した語が全角の本文へ当たる(self):
        applied = self.apply({"GUI": "_GUI_"}, "ＧＵＩの操作")
        self.assertEqual(applied, "|GUI|の操作")

    def test_大小文字は区別しない(self):
        applied = self.apply({"ＷｉＦｉ": "_ＷｉＦｉ_"}, "wifiの設定")
        self.assertEqual(applied, "|ＷｉＦｉ|の設定")

    def test_全角と半角が同じ本文に並んでもマーカーは増えない(self):
        applied = self.apply({"ＧＵＩ": "_ＧＵＩ_"}, "GUIとＧＵＩ")
        self.assertEqual(applied, "|ＧＵＩ|と|ＧＵＩ|")

    def test_登録が複数あっても順に当たる(self):
        applied = self.apply(
            {"台湾証券取引所": "台湾証券_取引所", "楽天モバイル": "_楽天モバイル_"},
            "台湾証券取引所と楽天モバイル",
        )
        self.assertEqual(applied, "台湾証券|取引所と|楽天モバイル|")

    def test_登録が無ければ本文はそのまま(self):
        self.assertEqual(self.apply({}, "台湾証券取引所"), "台湾証券取引所")


if __name__ == "__main__":
    unittest.main()
