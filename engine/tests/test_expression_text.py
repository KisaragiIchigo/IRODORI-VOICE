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
                    expected = text.replace("こんにちは。", "こんにちは..。") if text.startswith(annotation) else text.replace("晴れです！", "晴れです..！")
                    self.assertEqual(normalize_text(request.text), normalize_text(expected))
                    self.assertIn(annotation, normalize_text(request.text))

    def test_style_annotation_and_spacing(self):
        self.assertEqual(backend._apply_style_emoji("こんにちは。", "😊"), "😊こんにちは。")
        self.assertEqual(backend._apply_style_emoji("😠 こんにちは。", "😊"), "😠こんにちは。")
        self.assertEqual(backend._apply_style_emoji("こんにちは。😠 待って！", "😊"), "こんにちは。😠待って！")
        self.assertEqual(backend._apply_style_emoji("Hello World", None), "Hello World")

    def test_all_expression_captions_reach_request(self):
        from irodori_voice.backends.irodori.expression_caption import EXPRESSION_CAPTIONS
        from irodori_voice.settings import EngineSettings

        expected = set("😊 😆 😭 😠 🙄 😌 😟 😲 😖 🥺 👂 📣 😱 🐢 ⏩ 🤐 🫣 😏 😪 😴 🥱 🥴 😰 🤔 🤭 😮‍💨 ⏸️ 📞 📢 🎵 🥤 🤧 💋".split())
        self.assertEqual(set(EXPRESSION_CAPTIONS), expected)
        self.assertTrue(expected.issubset(annotations))
        instance = object.__new__(backend.IrodoriBackend)
        instance._settings = EngineSettings(num_steps=8)
        style = VoiceStyleDef(style_id="normal", name="確認用", emoji="😊", caption="落ち着いた男性の声。")
        preset = VoicePreset(
            preset_id="check", name="確認用", description="", color_key="shu",
            mode="caption", styles=[style], voice_seed=42,
        )
        for annotation in expected:
            for text in (annotation, f"{annotation} それは了解しました", f"それは了解しました{annotation}"):
                with self.subTest(text=text):
                    request = instance._build_request(
                        params=SynthesisParams(text=text, voice_id="irodori:check"),
                        preset=preset, style=style, runtime=None,
                    )
                    self.assertEqual(request.caption, style.caption + "\n" + EXPRESSION_CAPTIONS[annotation])
                    expected_text = text.replace(annotation + " ", annotation)
                    expected_text += ".."
                    self.assertEqual(request.text, expected_text)
                    self.assertIsNone(request.num_steps)

    def test_approved_sample_captions(self):
        from irodori_voice.backends.irodori.expression_caption import build_expression_caption

        for annotation, expected in (
            ("😭", "悲しみに耐えられず、涙を流して嗚咽しながら話している。"),
            ("🥺", "不安で心細く、声を震わせながら恐る恐る話している。"),
        ):
            self.assertEqual(
                build_expression_caption(annotation + "それは了解しました", style_caption=None, explicit_caption=None),
                expected,
            )

    def test_explicit_caption_takes_priority_including_empty(self):
        from irodori_voice.backends.irodori.expression_caption import build_expression_caption

        for explicit, expected in (("静かに話している。", "静かに話している。"), ("", None), ("  ", None)):
            self.assertEqual(
                build_expression_caption("😭それは了解しました", style_caption="男性の声。", explicit_caption=explicit),
                expected,
            )

    def test_repeated_and_composite_annotations(self):
        from irodori_voice.backends.irodori.expression_caption import build_expression_caption, EXPRESSION_CAPTIONS

        self.assertEqual(
            build_expression_caption("😮‍💨😮‍💨疲れました⏸️👂休みます", style_caption=None, explicit_caption=None),
            "\n".join(EXPRESSION_CAPTIONS[mark] for mark in ("😮‍💨", "⏸️", "👂")),
        )
        self.assertEqual(
            build_expression_caption("😭😭", style_caption=EXPRESSION_CAPTIONS["😭"], explicit_caption=None),
            EXPRESSION_CAPTIONS["😭"],
        )

    def test_no_automatic_caption_without_mapped_annotation(self):
        from irodori_voice.backends.irodori.expression_caption import build_expression_caption

        for text in ("", "それは了解しました", "😮", "😢", "😡", "🫶ありがとう"):
            for style_caption in (None, "", "  ", "男性の声。"):
                self.assertEqual(
                    build_expression_caption(text, style_caption=style_caption, explicit_caption=None),
                    style_caption if style_caption and style_caption.strip() else None,
                )


class ExpressionPauseTests(unittest.TestCase):
    def test_append_only_to_annotated_sentences(self):
        from irodori_voice.backends.irodori.expression_text import append_expression_pause

        cases = {
            "😭たえられず": "😭たえられず..",
            "😭たえられず。普通の文。": "😭たえられず..。普通の文。",
            "普通の文。😭たえられず！🥺ありがとう？": "普通の文。😭たえられず..！🥺ありがとう..？",
            "😭たえられず\n普通の文": "😭たえられず..\n普通の文",
            "😭たえられず  ": "😭たえられず..  ",
            "「😭たえられず」": "「😭たえられず..」",
            "": "",
            "普通の文です。": "普通の文です。",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(append_expression_pause(source), expected)
                self.assertEqual(append_expression_pause(expected), expected)

    def test_preserve_existing_ellipsis_and_all_annotations(self):
        from irodori_voice.backends.irodori.expression_text import append_expression_pause

        for ending in ("..", "...", "…", "……", "……。", "..！」"):
            text = "😭たえられず" + ending
            self.assertEqual(append_expression_pause(text), text)
        for annotation in annotations:
            self.assertEqual(append_expression_pause(annotation + "こんにちは"), annotation + "こんにちは..")


class PronunciationTests(unittest.TestCase):
    def test_example_matches_intelligible_sample(self):
        from irodori_voice.backends.irodori.pronunciation import apply_pronunciation

        text = "悲しみに耐えられず、涙を流して嗚咽しながら話している。"
        expected = "かなしみにたえられず、なみだをながしておえつしながらはなしている。"
        self.assertEqual(apply_pronunciation(text), expected)
        for annotation in annotations:
            with self.subTest(annotation=annotation):
                self.assertEqual(apply_pronunciation(annotation + text), annotation + expected)

    def test_preserves_kana_english_numbers_and_punctuation(self):
        from irodori_voice.backends.irodori.pronunciation import apply_pronunciation

        for text in ("", "かなしみにたえられず、なみだをながしておえつしながらはなしている。", "😮‍💨 Hello World 123.45%…⏸️", "カタカナ！「ほんとう？」"):
            self.assertEqual(apply_pronunciation(text), text)
        self.assertEqual(apply_pronunciation("悲しみ Hello World 123…😮‍💨"), "かなしみ Hello World 123…😮‍💨")

    def test_dictionary_reading_wins(self):
        from irodori_voice.backends.irodori.reading_overrides import apply_reading_overrides
        from irodori_voice.backends.irodori.pronunciation import apply_pronunciation

        text = apply_reading_overrides("嗚咽しながら話している。", [("嗚咽", "ムセビナキ")])
        self.assertEqual(apply_pronunciation(text), "むせびなきしながらはなしている。")

    def test_unknown_reading_keeps_original_text(self):
        from irodori_voice.backends.irodori.pronunciation import apply_pronunciation
        from irodori_voice.backends.irodori.word_boundaries import TokenSpan

        for reading in (None, "", "*", "、"):
            with patch("irodori_voice.backends.irodori.pronunciation.analyze", return_value=[TokenSpan(0, 1, reading)]):
                self.assertEqual(apply_pronunciation("字"), "字")
        with patch("irodori_voice.backends.irodori.pronunciation.analyze", return_value=None):
            self.assertEqual(apply_pronunciation("漢字😊"), "漢字😊")

    def test_katakana_conversion_covers_voiced_and_small_kana(self):
        from irodori_voice.backends.irodori.pronunciation import to_hiragana

        self.assertEqual(to_hiragana("カナシミ ヴァ ギャ ポッ ー ABC123😊"), "かなしみ ゔぁ ぎゃ ぽっ ー ABC123😊")


if __name__ == "__main__":
    unittest.main(verbosity=2)
