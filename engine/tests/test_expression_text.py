"""表現指定と読み編集の回帰確認。利用者の辞書は一時領域へ隔離する。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, resolution, query_memory, AudioQuery
    global backend, SynthesisParams, VoicePreset, VoiceStyleDef, annotations, normalize_text
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-expression-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice.routes.voicevox_compat import text_resolution as resolution
    from irodori_voice.routes.voicevox_compat.shared import query_memory
    from irodori_voice.voicevox.schemas import AudioQuery
    from irodori_voice.backends.irodori import backend
    from irodori_voice.backends.base import SynthesisParams
    from irodori_voice.voices.store import VoicePreset, VoiceStyleDef
    from irodori_voice.vendor.irodori_tts.duration import ALLOWED_ANNOTATION_EMOJIS as annotations
    from irodori_voice.vendor.irodori_tts.text_normalization import normalize_text


def tearDownModule():
    environment.stop()
    data_dir.cleanup()


class ExpressionTextTests(unittest.TestCase):
    def setUp(self):
        query_memory.clear()

    def query(self, text):
        return AudioQuery(accent_phrases=resolution.accent_phrases_for(text), kana=text)

    def test_same_reading_keeps_each_expression(self):
        texts = ["こんにちは。", "😊こんにちは。", "😠こんにちは。", "こんにちは！", "こんにちは？", "こんにちは…"]
        queries = [self.query(text) for text in texts]
        for text, query in zip(texts, queries):
            query_memory.remember(query.accent_phrases, text)
        for query, text in zip(queries, texts):
            with self.subTest(text=text):
                self.assertEqual(resolution._source_text_candidate(query), text)
                self.assertEqual(normalize_text(resolution.resolve_source_text(query)), normalize_text(text))

    def test_saved_query_works_without_memory(self):
        query = self.query("😮‍💨今日は疲れました……")
        restored = AudioQuery.model_validate_json(query.model_dump_json())
        self.assertEqual(resolution._source_text_candidate(restored), query.kana)
        self.assertEqual(normalize_text(resolution.resolve_source_text(restored)), normalize_text(query.kana))

    def test_changed_reading_overrides_old_source(self):
        query = self.query("😊こんにちは。")
        changed = resolution.accent_phrases_for("こんばんは。")
        query.accent_phrases = changed
        query_memory.remember(changed, "こんばんは。")
        self.assertEqual(resolution.resolve_source_text(query), "こんばんは。")
        query_memory.clear()
        self.assertEqual(
            resolution.resolve_source_text(query), resolution.accent_phrases_to_text(changed)
        )

    def test_client_without_source_uses_memory(self):
        query = self.query("🐢こんにちは。")
        query_memory.remember(query.accent_phrases, query.kana)
        query.kana = None
        self.assertEqual(resolution.resolve_source_text(query), "🐢こんにちは。")

    def test_current_text_applies_word_splits(self):
        from irodori_voice.voicevox.word_splits import apply_word_splits

        with patch("irodori_voice.voicevox.word_splits.load_splits", return_value={"証券取引所": "証券_取引所"}):
            text = "😊証券取引所です。"
            query = self.query(apply_word_splits(text))
            query.kana = text
            self.assertEqual(resolution.resolve_source_text(query), text)

    def test_annotation_without_spoken_text_is_preserved(self):
        query = self.query("😮‍💨")
        self.assertEqual(resolution.resolve_source_text(query), "😮‍💨")
        for text in ("", "※※※", "……"):
            with self.subTest(text=text):
                self.assertEqual(resolution.resolve_source_text(self.query(text)), "")

    def test_all_annotations_reach_sampling_request(self):
        from irodori_voice.settings import EngineSettings

        instance = object.__new__(backend.IrodoriBackend)
        instance._settings = EngineSettings()
        style = VoiceStyleDef(style_id="normal", name="確認用", emoji="😊")
        preset = VoicePreset(
            preset_id="check", name="確認用", description="", color_key="shu",
            mode="caption", styles=[style], voice_seed=42,
        )
        for annotation in annotations:
            for text in (f"{annotation}こんにちは。", f"こんにちは。{annotation}今日は晴れです！"):
                with self.subTest(text=text):
                    query = self.query(text)
                    query_memory.remember(query.accent_phrases, "別の文章です。")
                    request = instance._build_request(
                        params=SynthesisParams(text=resolution.resolve_source_text(query), voice_id="irodori:check"),
                        preset=preset, style=style, runtime=None,
                    )
                    self.assertEqual(normalize_text(request.text), normalize_text(text))
                    self.assertIn(annotation, normalize_text(request.text))

    def test_style_annotation_and_spacing(self):
        self.assertEqual(backend._apply_style_emoji("こんにちは。", "😊"), "😊こんにちは。")
        self.assertEqual(backend._apply_style_emoji("😠 こんにちは。", "😊"), "😠こんにちは。")
        self.assertEqual(backend._apply_style_emoji("こんにちは。😠 待って！", "😊"), "こんにちは。😠待って！")
        self.assertEqual(backend._apply_style_emoji("Hello World", None), "Hello World")


if __name__ == "__main__":
    unittest.main(verbosity=2)
