"""話者のスタイル一覧と、あとから書き足すメモを検証する。

借りた声とシードの声で同じ顔ぶれが付くこと、既にある話者へ足しても既存の定義と
エディタ側の割り当てが変わらないこと、メモが保存と再読み込みをまたいで残ることを見る。
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def setUpModule():
    global data_dir, environment, paths, seed_bake, clone, expression_styles
    global VoicePresetStore, VoiceStyleDef, style_id_for
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-voice-styles-")
    environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name})
    environment.start()
    from irodori_voice import paths
    from irodori_voice.voices import clone, expression_styles, seed_bake
    from irodori_voice.voices.store import VoicePresetStore, VoiceStyleDef
    from irodori_voice.voicevox.speaker_map import style_id_for
    paths.user_data_root.cache_clear()


def tearDownModule():
    paths.user_data_root.cache_clear()
    environment.stop()
    data_dir.cleanup()


class ExpressionStyleTests(unittest.TestCase):
    def seed_voice(self, store, **kwargs):
        with patch.object(seed_bake, "bake_seed_reference", return_value=["参照.wav"]):
            return seed_bake.create_voice_from_seed(
                irodori=Mock(), store=store, name="試験", seed=7, **kwargs
            )

    def test_seed_voice_gets_the_same_styles_as_a_borrowed_voice(self):
        voice = self.seed_voice(VoicePresetStore([]))
        names = [style.style_id for style in voice.styles]
        self.assertEqual(names, [row[0] for row in expression_styles.EXPRESSION_STYLES])
        self.assertEqual(voice.styles[0].style_id, "normal")
        self.assertIsNone(voice.styles[0].emoji)
        # 表現の条件は採用済みのシード向け設定のまま、どのスタイルにも乗る。
        for style in voice.styles:
            self.assertEqual(
                (style.num_steps, style.cfg_scale_caption, style.cfg_scale_speaker),
                (40, 5.0, 3.0),
            )
        joy = next(style for style in voice.styles if style.style_id == "joy")
        self.assertEqual(joy.emoji, "😆")
        self.assertEqual(joy.caption, "弾むように、嬉しそうに話している。")

    def test_seed_caption_stays_on_normal_only(self):
        voice = self.seed_voice(VoicePresetStore([]), caption="低い声で話している。")
        self.assertEqual(voice.styles[0].caption, "低い声で話している。")
        for style in voice.styles[1:]:
            self.assertNotEqual(style.caption, "低い声で話している。")

    def test_seed_voice_can_be_created_without_emotion_styles(self):
        voice = self.seed_voice(VoicePresetStore([]), with_emotion_styles=False)
        self.assertEqual([style.style_id for style in voice.styles], ["normal"])

    def test_clone_and_seed_share_one_table(self):
        borrowed = expression_styles.build_expression_styles(
            VoiceStyleDef(style_id="normal", name="ノーマル", cfg_scale_speaker=3.0)
        )
        seeded = self.seed_voice(VoicePresetStore([])).styles
        self.assertEqual(
            [(style.style_id, style.name, style.emoji) for style in borrowed],
            [(style.style_id, style.name, style.emoji) for style in seeded],
        )
        self.assertEqual(borrowed[0].cfg_scale_speaker, clone.REFERENCE_SPEAKER_CFG)
        # ノーマルはキャプションを持たない。喋り方の指示の効きは喜怒哀楽にだけ乗る。
        self.assertIsNone(borrowed[0].caption)

    def test_borrowed_voice_generation_values_survive_the_table(self):
        # 表が差し替えるのは識別子・表示名・キャプション・絵文字だけで、生成条件は土台のまま。
        template = VoiceStyleDef(
            style_id="normal",
            name="ノーマル",
            cfg_scale_speaker=clone.REFERENCE_SPEAKER_CFG,
            cfg_scale_caption=clone.REFERENCE_CAPTION_CFG,
            num_steps=clone.REFERENCE_NUM_STEPS,
        )
        for style in expression_styles.build_expression_styles(template):
            with self.subTest(style=style.style_id):
                self.assertEqual(style.cfg_scale_speaker, clone.REFERENCE_SPEAKER_CFG)
                self.assertEqual(style.cfg_scale_caption, clone.REFERENCE_CAPTION_CFG)
                self.assertEqual(style.num_steps, clone.REFERENCE_NUM_STEPS)

    def test_adding_styles_keeps_existing_definitions_and_editor_ids(self):
        store = VoicePresetStore([])
        voice = store.create(
            name="ノーマルだけ", description="", color_key="shu", mode="reference",
            styles=[VoiceStyleDef(style_id="normal", name="ノーマル", caption="低い声。", num_steps=40)],
            reference_files=["参照.wav"], voice_seed=7,
        )
        before = style_id_for(f"irodori:{voice.preset_id}", "normal")

        extended = expression_styles.extend_with_expression_styles(voice.styles)
        updated = store.update(voice.preset_id, {"styles": [s.to_json() for s in extended]})

        self.assertEqual(len(updated.styles), len(expression_styles.EXPRESSION_STYLES))
        self.assertEqual(updated.styles[0].to_json(), voice.styles[0].to_json())
        self.assertEqual(style_id_for(f"irodori:{updated.preset_id}", "normal"), before)
        # 土台はノーマル。生成条件はその話者の値を引き継ぐ。
        self.assertTrue(all(style.num_steps == 40 for style in updated.styles))
        # もう一度当てても増えない。
        again = expression_styles.extend_with_expression_styles(updated.styles)
        self.assertEqual([s.to_json() for s in again], [s.to_json() for s in updated.styles])

    def test_baking_an_unfixed_voice_also_fills_in_the_styles(self):
        store = VoicePresetStore([])
        voice = store.create(
            name="未固定", description="", color_key="shu", mode="caption", voice_seed=42,
            styles=[VoiceStyleDef(style_id="normal", name="通常")],
        )
        with patch.object(seed_bake, "bake_seed_reference", return_value=["固定.wav"]):
            result = seed_bake.bake_existing_voice(
                irodori=Mock(), store=store, preset_id=voice.preset_id
            )
        self.assertEqual(len(result.styles), len(expression_styles.EXPRESSION_STYLES))
        # 元からあったスタイルは表示名ごと残す。エディタが覚えている名前が変わらない。
        self.assertEqual(result.styles[0].name, "通常")
        self.assertEqual(result.styles[1].num_steps, 40)


class ExpressionStyleRouteTests(unittest.TestCase):
    """あとからスタイルを足す口の、受け付けと断り方。"""

    def call(self, store, voice_id):
        from types import SimpleNamespace
        from irodori_voice.routes.voices.crud import add_expression_styles

        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    engine=SimpleNamespace(store=store, irodori=Mock(), service=Mock(), registry=None)
                )
            )
        )
        return add_expression_styles(request, voice_id)

    def test_refuses_voices_that_cannot_take_styles(self):
        from fastapi import HTTPException
        from irodori_voice.voices.presets import BUILTIN_PRESETS

        store = VoicePresetStore(BUILTIN_PRESETS)
        unfixed = store.create(
            name="未固定", description="", color_key="shu", mode="caption",
            styles=[VoiceStyleDef(style_id="normal", name="ノーマル")],
        )
        cases = {
            f"irodori:{BUILTIN_PRESETS[0].preset_id}": 403,
            f"irodori:{unfixed.preset_id}": 400,
            "irodori:missing": 404,
            "aivm:model/0": 400,
        }
        for voice_id, status in cases.items():
            with self.subTest(voice_id=voice_id):
                with self.assertRaises(HTTPException) as error:
                    self.call(store, voice_id)
                self.assertEqual(error.exception.status_code, status)

    def test_fills_in_the_styles_of_a_fixed_voice(self):
        from irodori_voice.voices import expression_styles as table

        store = VoicePresetStore([])
        voice = store.create(
            name="固定済み", description="", color_key="shu", mode="reference",
            styles=[VoiceStyleDef(style_id="normal", name="ノーマル")],
            reference_files=["参照.wav"], voice_seed=7,
        )
        # 応答の整形は話者一覧のバックエンドを要するため、ここでは素通しにする。
        with patch("irodori_voice.routes.voices.crud.voice_out_for_preset", lambda state, preset: preset):
            result = self.call(store, f"irodori:{voice.preset_id}")
        self.assertEqual(len(result.styles), len(table.EXPRESSION_STYLES))
        self.assertEqual(len(store.get(voice.preset_id).styles), len(table.EXPRESSION_STYLES))


class VoiceMemoTests(unittest.TestCase):
    def test_memo_survives_save_reload_and_duplicate(self):
        store = VoicePresetStore([])
        voice = store.create(
            name="メモ付き", description="シード 7 から作った話者", color_key="shu",
            mode="caption", styles=[VoiceStyleDef(style_id="normal", name="ノーマル")],
        )
        self.assertEqual(voice.memo, "")

        store.update(voice.preset_id, {"memo": "第3話のナレーション用。少し低め。"})
        reloaded = VoicePresetStore([]).get(voice.preset_id)
        duplicate = store.duplicate(voice.preset_id)
        self.assertEqual(reloaded.memo, "第3話のナレーション用。少し低め。")
        self.assertEqual(duplicate.memo, "第3話のナレーション用。少し低め。")
        # 説明は作り方の記録なので、メモを書いても残る。
        self.assertEqual(reloaded.description, "シード 7 から作った話者")

        store.update(voice.preset_id, {"memo": ""})
        self.assertEqual(VoicePresetStore([]).get(voice.preset_id).memo, "")

    def test_memo_is_optional_in_saved_files(self):
        """メモを持たない話者ファイル（この機能より前に作ったもの）も読める。"""

        from irodori_voice.voices.store import VoicePreset
        preset = VoicePreset.from_json(
            {
                "preset_id": "user-old", "name": "以前の話者", "description": "",
                "color_key": "shu", "mode": "caption",
                "styles": [{"style_id": "normal", "name": "ノーマル"}],
            }
        )
        self.assertEqual(preset.memo, "")

    def test_api_limits_memo_length_and_separates_empty_from_unset(self):
        from pydantic import ValidationError
        from irodori_voice.schemas import MAX_MEMO_LENGTH, VoiceUpdateRequest

        cleared = VoiceUpdateRequest(memo="")
        self.assertEqual(cleared.model_dump(exclude_none=True), {"memo": ""})
        self.assertEqual(VoiceUpdateRequest().model_dump(exclude_none=True), {})
        VoiceUpdateRequest(memo="あ" * MAX_MEMO_LENGTH)
        with self.assertRaises(ValidationError):
            VoiceUpdateRequest(memo="あ" * (MAX_MEMO_LENGTH + 1))


if __name__ == "__main__":
    unittest.main()
