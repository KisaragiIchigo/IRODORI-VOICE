"""話者一覧の試聴音声の作り置きが、話者の定義の変更に追従することを検証する。

同梱話者は ID もファイル名も変えずに参照音声や生成条件を差し替えるため、ID だけを鍵にすると
古い音が鳴り続ける。
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
    global data_dir, cache_dir, environment, paths, sample_voice, VoicePreset, VoiceStyleDef
    data_dir = tempfile.TemporaryDirectory(prefix="irodori-sample-data-")
    cache_dir = tempfile.TemporaryDirectory(prefix="irodori-sample-cache-")
    environment = patch.dict(
        os.environ, {"IRODORI_VOICE_DATA_DIR": data_dir.name, "IRODORI_VOICE_CACHE_DIR": cache_dir.name}
    )
    environment.start()
    from irodori_voice import paths
    from irodori_voice.voicevox import sample_voice
    from irodori_voice.voices.store import VoicePreset, VoiceStyleDef
    paths.user_data_root.cache_clear()
    paths.cache_root.cache_clear()


def tearDownModule():
    paths.user_data_root.cache_clear()
    paths.cache_root.cache_clear()
    environment.stop()
    data_dir.cleanup()
    cache_dir.cleanup()


def preset(reference: Path, caption: str = "明るい声。") -> VoicePreset:
    return VoicePreset(
        preset_id="user-sample", name="確認用", description="", color_key="shu", mode="reference",
        styles=[VoiceStyleDef(style_id="normal", name="ノーマル", caption=caption)],
        reference_files=[reference.name], voice_seed=7,
    )


class RevisionTests(unittest.TestCase):
    def test_changes_with_the_style_and_the_reference(self):
        reference = paths.voice_assets_dir() / "ref-sample.wav"
        reference.write_bytes(b"RIFF1")
        base = preset(reference).revision("normal")
        self.assertEqual(preset(reference).revision("normal"), base)
        self.assertNotEqual(preset(reference, caption="朗読している。").revision("normal"), base)
        reference.write_bytes(b"RIFF-longer")
        self.assertNotEqual(preset(reference).revision("normal"), base)


class SampleStoreTests(unittest.TestCase):
    def setUp(self):
        for path in sample_voice._sample_dir().glob("*"):
            path.unlink()

    def run_worker(self, store, voice_id, style_id):
        store.samples_for(voice_id, style_id)
        worker = store._worker
        if worker is not None:
            worker.join(timeout=5)

    def test_new_definition_is_generated_and_the_old_one_removed(self):
        revision = {"value": "aaa111"}
        made = []

        def generate(voice_id, style_id, text):
            made.append(revision["value"])
            return b"RIFF-" + revision["value"].encode()

        store = sample_voice.SampleVoiceStore()
        store.bind(generate, lambda voice_id, style_id: revision["value"])
        old_format = sample_voice._sample_path("irodori:child-girl", "normal", 0)
        old_format.write_bytes(b"RIFF-before")

        self.run_worker(store, "irodori:child-girl", "normal")
        revision["value"] = "bbb222"
        self.run_worker(store, "irodori:child-girl", "normal")

        self.assertEqual(made, ["aaa111", "bbb222"])
        remaining = sorted(p.name for p in sample_voice._sample_dir().glob("*.wav"))
        self.assertEqual(remaining, [sample_voice._sample_path("irodori:child-girl", "normal", 0, "bbb222").name])
        self.assertEqual(len(store.samples_for("irodori:child-girl", "normal")), 1)

    def test_voices_without_a_revision_keep_their_samples(self):
        store = sample_voice.SampleVoiceStore()
        store.bind(lambda *args: b"RIFF-new", lambda voice_id, style_id: "")
        existing = sample_voice._sample_path("aivm:model/0", "0", 0)
        existing.write_bytes(b"RIFF-kept")
        self.run_worker(store, "aivm:model/0", "0")
        self.assertEqual(existing.read_bytes(), b"RIFF-kept")


if __name__ == "__main__":
    unittest.main()
