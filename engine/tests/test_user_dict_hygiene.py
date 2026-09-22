"""辞書の登録内容の衛生と、辞書を書き換えたときのキャッシュ破棄を確認する。

表記へ改行が混ざると CSV が途中で折れ、OpenJTalk がその行と巻き添えの行を捨てる。
また、合成キャッシュの鍵は辞書を当てる前の生の本文なので、辞書を変えただけでは鍵が
変わらない。捨て忘れると「登録したのに前の読みが再生される」ことになる。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, word, compat_word_splits, compat_shared
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-dict-hygiene-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice.voicevox.user_dict import word
    from irodori_voice.routes.voicevox_compat import shared as compat_shared
    from irodori_voice.routes.voicevox_compat import word_splits as compat_word_splits


def tearDownModule():
    environment.stop()
    data_dir.cleanup()


class FieldHygieneTests(unittest.TestCase):
    def test_改行と制御文字と前後の空白を落とす(self):
        self.assertEqual(word.normalize_field("翌々月末\n"), "翌々月末")
        self.assertEqual(word.normalize_field("\r\n証券取引所\t"), "証券取引所")
        self.assertEqual(word.normalize_field("  相棒  "), "相棒")
        self.assertEqual(word.normalize_field("全角\u3000空白"), "全角空白")

    def test_保存済みの壊れた語も読み込みで直る(self):
        # 既に改行つきで保存されている語は、次に読み込んだ時点で直る。
        broken = word.UserDictWord.from_json(
            {
                "surface": "翌々月末\n", "priority": 10, "context_id": 1348,
                "part_of_speech": "名詞", "part_of_speech_detail_1": "固有名詞",
                "part_of_speech_detail_2": "一般", "part_of_speech_detail_3": "*",
                "inflectional_type": "*", "inflectional_form": "*", "stem": "*",
                "yomi": "ヨクヨクツキマツ", "pronunciation": "ヨクヨクツキマツ",
                "accent_type": 0, "mora_count": 8,
            }
        )
        self.assertEqual(broken.surface, "翌々月末")
        # CSV が途中で折れないことが肝心。折れると OpenJTalk がその行を捨てる。
        self.assertNotIn("\n", broken.to_csv_row())

    def test_表記や読みが空になる登録は弾く(self):
        for surface, pronunciation in ((" \n ", "アイ"), ("相棒", "\t")):
            with self.subTest(surface=surface, pronunciation=pronunciation):
                with self.assertRaises(ValueError):
                    word.UserDictWord.build(
                        surface=surface, pronunciation=pronunciation, accent_type=0
                    )

    def test_まっとうな登録はそのまま通る(self):
        built = word.UserDictWord.build(
            surface="証券取引所", pronunciation="ショウケントリヒキジョ", accent_type=0
        )
        self.assertEqual(built.surface, "証券取引所")
        self.assertEqual(built.pronunciation, "ショウケントリヒキジョ")


class CacheInvalidationTests(unittest.TestCase):
    def request_with(self, service):
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            engine=SimpleNamespace(service=service)
        )))

    def test_フレーズ分割辞書を書き換えたらキャッシュを捨てる(self):
        service = Mock()
        with patch.object(compat_word_splits, "save_splits") as save:
            compat_word_splits.update_word_splits(
                self.request_with(service), {"証券取引所": "_証券取引所_"}
            )
        save.assert_called_once_with({"証券取引所": "_証券取引所_"})
        service.clear_cache.assert_called_once()

    def test_起動しきる前でも落ちない(self):
        # 合成サービスがまだ組み立てられていない時間帯がある。
        with patch.object(compat_word_splits, "save_splits"):
            compat_word_splits.update_word_splits(self.request_with(None), {})
        compat_shared.invalidate_audio_cache(self.request_with(None))


if __name__ == "__main__":
    unittest.main()
