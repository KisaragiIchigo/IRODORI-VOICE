"""シード話者の表現設定と生成回数の優先順位を検証する。"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, paths, seed_bake, VoicePresetStore, VoicePreset, VoiceStyleDef
    global IrodoriBackend, SynthesisParams, EngineSettings, apply_seed_expression_profile
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-seed-profile-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice import paths
    from irodori_voice.voices import seed_bake
    from irodori_voice.voices.store import VoicePresetStore, VoicePreset, VoiceStyleDef
    from irodori_voice.voices.seed_profile import apply_seed_expression_profile
    from irodori_voice.backends.irodori.backend import IrodoriBackend
    from irodori_voice.backends.base import SynthesisParams
    from irodori_voice.settings import EngineSettings
    paths.user_data_root.cache_clear()


def tearDownModule():
    paths.user_data_root.cache_clear()
    environment.stop()
    data_dir.cleanup()


class SeedProfileTests(unittest.TestCase):
    def request(self, style, *, steps=None, global_steps=8, reference=True,
                voice_seed=114514, text="😭こんにちは。", design_steps=None,
                pronunciation_mode="off"):
        instance = object.__new__(IrodoriBackend)
        instance._settings = EngineSettings(
            num_steps=global_steps,
            voice_design_steps=design_steps,
            pronunciation_mode=pronunciation_mode,
        )
        instance._reference_cache = Mock()
        instance._reference_cache.resolve.return_value = ["参照.pt"]
        preset = VoicePreset(
            preset_id="test", name="確認用", description="", color_key="shu",
            mode="reference" if reference else "caption", styles=[style],
            reference_files=["参照.wav"] if reference else [], voice_seed=voice_seed,
        )
        return instance._build_request(
            params=SynthesisParams(text=text, voice_id="irodori:test", steps=steps),
            preset=preset, style=style, runtime=None,
        )

    def test_profile_reaches_request_without_replacing_reference_or_seed(self):
        style = apply_seed_expression_profile(VoiceStyleDef(style_id="normal", name="通常"))
        request = self.request(style)
        self.assertEqual((request.num_steps, request.cfg_scale_caption, request.cfg_scale_speaker), (40, 5.0, 3.0))
        self.assertEqual(request.cfg_scale_text, 3.0)
        self.assertEqual(request.ref_latents, ["参照.pt"])
        self.assertEqual(request.seed, 114514)
        self.assertFalse(request.no_ref)
        self.assertIn("嗚咽", request.caption)

    def test_explicit_steps_override_style_and_style_overrides_engine(self):
        style = apply_seed_expression_profile(VoiceStyleDef(style_id="normal", name="通常"))
        self.assertEqual(self.request(style, steps=12).num_steps, 12)
        self.assertEqual(self.request(style, global_steps=64).num_steps, 40)
        old_style = VoiceStyleDef.from_json({"style_id": "normal", "name": "通常"})
        self.assertEqual(self.request(old_style).num_steps, 8)
        self.assertIsNone(self.request(old_style, global_steps=None).num_steps)

    def test_reference_free_uses_model_defaults_despite_old_engine_settings(self):
        style = VoiceStyleDef(style_id="normal", name="通常")
        request = self.request(style, reference=False)
        self.assertIsNone(request.num_steps)
        self.assertEqual(request.cfg_scale_caption, 3.0)
        self.assertEqual(request.cfg_scale_text, 3.0)
        self.assertTrue(request.no_ref)

    def test_reference_free_respects_explicit_steps_and_text_guidance(self):
        style = VoiceStyleDef(style_id="normal", name="通常", cfg_scale_text=2.0)
        self.assertEqual(self.request(style, reference=False, steps=12).num_steps, 12)
        self.assertEqual(self.request(style, reference=False).cfg_scale_text, 2.0)
        self.assertEqual(self.request(style, reference=False, design_steps=32).num_steps, 32)
        style.num_steps = 24
        self.assertEqual(self.request(style, reference=False).num_steps, 24)

    def test_seed_voices_preserve_original_text_and_dictionary_overrides(self):
        style = VoiceStyleDef(style_id="normal", name="通常")
        with patch("irodori_voice.backends.irodori.backend.shared_user_dict") as dictionary:
            dictionary.return_value.reading_overrides.return_value = [("嗚咽", "ムセビナキ")]
            for reference in (False, True):
                request = self.request(style, reference=reference, text="嗚咽しながら話している。")
                self.assertEqual(request.text, "むせびなきしながら話している。")
                self.assertIsNone(request.caption)
            # 借りた声も、既定では表記のまま渡る。読みの置き換えは設定で選んだときだけ。
            borrowed = self.request(style, voice_seed=None, text="嗚咽しながら話している。")
            self.assertEqual(borrowed.text, "むせびなきしながら話している。")
            explicit = self.request(
                style, voice_seed=None, text="嗚咽しながら話している。", pronunciation_mode="kanji"
            )
            self.assertEqual(explicit.text, "むせびなきしながらはなしている。")
            # シードで固定した声は、読みを明示する設定でも表記のまま渡る。
            fixed = self.request(style, text="嗚咽しながら話している。", pronunciation_mode="kanji")
            self.assertEqual(fixed.text, "むせびなきしながら話している。")

    def test_builtin_voices_use_quality_defaults_without_erasing_style(self):
        from irodori_voice.voices.presets import BUILTIN_PRESETS
        for preset in BUILTIN_PRESETS:
            style = preset.styles[0]
            request = self.request(style, reference=False, voice_seed=None, text="今日は晴れです。")
            self.assertEqual(request.text, "今日は晴れです。")
            self.assertEqual(request.caption, style.caption)
            self.assertEqual(request.cfg_scale_text, 3.0)
            self.assertIsNone(request.num_steps)

    def test_saved_eight_step_settings_do_not_lower_voice_design_quality(self):
        settings = EngineSettings.from_json({"num_steps": 8})
        self.assertEqual(settings.num_steps, 8)
        self.assertIsNone(settings.voice_design_steps)

    def test_borrowed_voice_keeps_existing_settings(self):
        style = VoiceStyleDef(style_id="normal", name="通常", cfg_scale_speaker=3.0)
        request = self.request(style)
        self.assertEqual((request.num_steps, request.cfg_scale_caption, request.cfg_scale_speaker), (8, 3.0, 3.0))

    def test_profile_preserves_other_style_values(self):
        style = VoiceStyleDef(style_id="joy", name="喜び", caption="明るい声。", emoji="😆", duration_scale=1.2, cfg_scale_text=4.0)
        updated = apply_seed_expression_profile(style)
        for field in ("style_id", "name", "caption", "emoji", "duration_scale", "cfg_scale_text"):
            self.assertEqual(getattr(updated, field), getattr(style, field))
        self.assertIsNone(style.num_steps)

    def test_new_seed_profile_survives_save_reload_and_duplicate(self):
        store = VoicePresetStore([])
        with patch.object(seed_bake, "bake_seed_reference", return_value=["元の参照.wav"]):
            voice = seed_bake.create_voice_from_seed(irodori=Mock(), store=store, name="試験", seed=0)
        reloaded = VoicePresetStore([]).get(voice.preset_id)
        duplicate = store.duplicate(voice.preset_id)
        for candidate in (voice, reloaded, duplicate):
            request = self.request(candidate.styles[0])
            self.assertEqual((request.num_steps, request.cfg_scale_caption, request.cfg_scale_speaker), (40, 5.0, 3.0))
            self.assertEqual(candidate.reference_files, ["元の参照.wav"])
            self.assertEqual(candidate.voice_seed, 0)

    def test_existing_unfixed_voice_gets_profile_when_baked(self):
        store = VoicePresetStore([])
        voice = store.create(name="未固定", description="", color_key="shu", mode="caption", voice_seed=42,
                             styles=[VoiceStyleDef(style_id="normal", name="通常")])
        with patch.object(seed_bake, "bake_seed_reference", return_value=["固定.wav"]):
            result = seed_bake.bake_existing_voice(irodori=Mock(), store=store, preset_id=voice.preset_id)
        self.assertEqual(result.mode, "reference")
        self.assertEqual(result.voice_seed, 42)
        self.assertEqual(result.styles[0].num_steps, 40)
        self.assertEqual(result.styles[0].cfg_scale_caption, 5.0)
        self.assertEqual(result.styles[0].cfg_scale_speaker, 3.0)

    def test_seed_sources_copy_style_without_copying_voice_identity(self):
        from irodori_voice.voices.seed_source import create_seed_preset
        store = VoicePresetStore([])
        for mode in ("caption", "reference", "embed"):
            with self.subTest(mode=mode):
                source = store.create(
                    name="元の声", description="", color_key="shu", mode=mode,
                    styles=[VoiceStyleDef(style_id="base", name="基本", caption="落ち着いた声", num_steps=24)],
                    reference_files=["参照.wav"] if mode == "reference" else [],
                    speaker_embed_file="声.pt" if mode == "embed" else None, voice_seed=99,
                )
                before = source.to_json()
                temporary = create_seed_preset(store, seed=0, caption=None, source_voice_id=f"irodori:{source.preset_id}")
                self.assertEqual(temporary.mode, "caption")
                self.assertEqual(temporary.reference_files, [])
                self.assertIsNone(temporary.speaker_embed_file)
                self.assertEqual(temporary.voice_seed, 0)
                self.assertEqual(temporary.styles[0].caption, "落ち着いた声")
                self.assertEqual(temporary.styles[0].num_steps, 80)
                backend = object.__new__(IrodoriBackend)
                backend._settings = EngineSettings()
                backend._reference_cache = Mock()
                request = backend._build_request(
                    params=SynthesisParams(text="確認です。", voice_id=f"irodori:{temporary.preset_id}"),
                    preset=temporary, style=temporary.styles[0], runtime=None,
                )
                self.assertTrue(request.no_ref)
                self.assertEqual(request.seed, 0)
                self.assertEqual(request.caption, "落ち着いた声")
                self.assertEqual(request.num_steps, 80)
                self.assertEqual(request.cfg_scale_text, 2.0)
                self.assertIsNone(request.ref_embed)
                backend._reference_cache.resolve.assert_not_called()
                temporary.styles[0].caption = "別の指示"
                temporary.reference_files.append("追加.wav")
                self.assertEqual(source.to_json(), before)
                overridden = create_seed_preset(store, seed=1, caption="明るい声", source_voice_id=f"irodori:{source.preset_id}")
                self.assertEqual(overridden.styles[0].caption, "明るい声")

    def test_seed_source_default_and_invalid_ids(self):
        from irodori_voice.voices.seed_source import create_seed_preset
        from irodori_voice.backends.base import BackendError
        store = VoicePresetStore([])
        temporary = create_seed_preset(store, seed=0, caption=None)
        self.assertEqual((temporary.mode, temporary.voice_seed, temporary.reference_files), ("caption", 0, []))
        request = self.request(temporary.styles[0], reference=False, text="確認です。", design_steps=8)
        self.assertEqual((request.num_steps, request.cfg_scale_text), (80, 2.0))
        self.assertIsNone(request.caption)
        for source_id in ("aivm:test", "irodori:missing"):
            with self.assertRaises(BackendError):
                create_seed_preset(store, seed=0, caption=None, source_voice_id=source_id)

    def test_preview_and_save_use_same_source_and_clean_up_on_failure(self):
        from types import SimpleNamespace
        from irodori_voice.routes.voices.preview import preview_seed
        from irodori_voice.schemas import SeedPreviewRequest
        from irodori_voice.backends.base import BackendError
        from fastapi import HTTPException
        store = VoicePresetStore([])
        source = store.create(
            name="元の声", description="", color_key="shu", mode="reference", voice_seed=99,
            styles=[VoiceStyleDef(style_id="base", name="基本", caption="低い声")], reference_files=["参照.wav"],
        )
        captured = []
        def fail(params):
            preset = store.get(params.voice_id.removeprefix("irodori:"))
            captured.append((preset.mode, preset.reference_files, preset.voice_seed, preset.styles[0].to_json()))
            raise BackendError("合成失敗の検証")
        backend = Mock()
        backend.synthesize.side_effect = fail
        service = Mock()
        service.synthesize.side_effect = fail
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=SimpleNamespace(
            store=store, irodori=backend, service=service,
        ))))
        source_id = f"irodori:{source.preset_id}"
        before = [preset.preset_id for preset in store.list()]
        with self.assertRaises(HTTPException) as error:
            preview_seed(request, SeedPreviewRequest(seed=0, source_voice_id=source_id))
        self.assertEqual(error.exception.status_code, 400)
        with self.assertRaises(BackendError):
            seed_bake.create_voice_from_seed(irodori=backend, store=store, name="保存", seed=0, source_voice_id=source_id)
        self.assertEqual(captured[0], captured[1])
        self.assertEqual(captured[0][:3], ("caption", [], 0))
        self.assertEqual([preset.preset_id for preset in store.list()], before)
        with self.assertRaises(HTTPException) as error:
            preview_seed(request, SeedPreviewRequest(seed=0, source_voice_id="irodori:missing"))
        self.assertEqual(error.exception.status_code, 400)

    def test_bake_saves_four_references_and_removes_temporary_voices(self):
        from types import SimpleNamespace
        import numpy as np
        from irodori_voice.voices.reference import SEED_FOLLOWUP_TEXTS, SEED_REFERENCE_TEXT
        store = VoicePresetStore([])
        read: list[str] = []

        def synthesize(params):
            preset = store.get(params.voice_id.removeprefix("irodori:"))
            # 1 本目は参照を持たない話者で焼き、2 本目からはその 1 本目を参照に据える。
            if read:
                self.assertEqual(preset.mode, "reference")
                self.assertEqual(len(preset.reference_files), 1)
            else:
                self.assertEqual(preset.mode, "caption")
            read.append(params.text)
            return SimpleNamespace(samples=np.zeros(24000, dtype=np.float32), sample_rate=48000)

        backend = Mock()
        backend.synthesize.side_effect = synthesize
        before = [preset.preset_id for preset in store.list()]
        names = seed_bake.bake_seed_reference(irodori=backend, store=store, seed=7, caption=None)

        self.assertEqual(len(names), 4)
        self.assertEqual(len(set(names)), 4)
        for name in names:
            self.assertTrue((paths.voice_assets_dir() / name).exists())
        # 助走の無い参照は生成音声の冒頭を破裂させるため、先頭へ無音を足して保存する。
        import wave
        from irodori_voice.voices.reference import SEED_REFERENCE_LEAD_SECONDS
        for name in names:
            with wave.open(str(paths.voice_assets_dir() / name), "rb") as saved:
                lead = int(saved.getframerate() * SEED_REFERENCE_LEAD_SECONDS)
                self.assertEqual(saved.getnframes(), 24000 + lead)
                head = saved.readframes(lead)
                self.assertEqual(set(head), {0})
        self.assertEqual(read[0], SEED_REFERENCE_TEXT)
        self.assertEqual(read[1:], list(SEED_FOLLOWUP_TEXTS))
        # 焼き終わったあとに一時の話者を残さない。
        self.assertEqual([preset.preset_id for preset in store.list()], before)

    def test_bake_does_not_leave_orphan_reference_when_followup_fails(self):
        from types import SimpleNamespace
        import numpy as np
        from irodori_voice.backends.base import BackendError
        store = VoicePresetStore([])
        done: list[str] = []

        def synthesize(params):
            if done:
                raise BackendError("2 本目の失敗を検証する")
            done.append(params.text)
            return SimpleNamespace(samples=np.zeros(24000, dtype=np.float32), sample_rate=48000)

        backend = Mock()
        backend.synthesize.side_effect = synthesize
        existing = {path.name for path in paths.voice_assets_dir().glob("ref-*.wav")}
        with self.assertRaises(BackendError):
            seed_bake.bake_seed_reference(irodori=backend, store=store, seed=7, caption=None)
        # 1 本目を書き出したあとに失敗しても、ファイルを置き去りにしない。
        self.assertEqual({path.name for path in paths.voice_assets_dir().glob("ref-*.wav")}, existing)
        self.assertEqual(store.list(), [])

    def test_api_accepts_and_validates_style_steps(self):
        from pydantic import ValidationError
        from irodori_voice.schemas import VoiceUpdateRequest
        for value in (None, 1, 40, 128):
            payload = VoiceUpdateRequest(styles=[{"style_id": "normal", "name": "通常", "num_steps": value}])
            self.assertEqual(payload.model_dump(exclude_unset=True)["styles"][0]["num_steps"], value)
        for value in (0, -1, 129):
            with self.assertRaises(ValidationError):
                VoiceUpdateRequest(styles=[{"style_id": "normal", "name": "通常", "num_steps": value}])


if __name__ == "__main__":
    unittest.main()
