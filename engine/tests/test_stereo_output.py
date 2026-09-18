"""左右の保持、既定ステレオ、モノラルとの結合を検証する。"""

import base64
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from irodori_voice import audio
from irodori_voice.backends.base import SynthesisOutput
from irodori_voice.synthesis.steps.apply_output_format import OutputFormat, apply_output_format


class StereoOutputTests(unittest.TestCase):
    def test_default_stereo_preserves_mono_level_and_duration(self):
        source = np.linspace(-.5, .5, 4800, dtype=np.float32)
        result = apply_output_format(source, source_rate=48000, output=OutputFormat())
        samples, rate = sf.read(io.BytesIO(result.wav), dtype="float32")
        self.assertEqual(samples.shape, (4800, 2))
        self.assertEqual(rate, 48000)
        self.assertEqual(result.duration_seconds, .1)
        np.testing.assert_array_equal(samples[:, 0], samples[:, 1])
        np.testing.assert_allclose(samples[:, 0], source, atol=1/32768, rtol=0)
        mono = apply_output_format(source, source_rate=48000, output=OutputFormat(stereo=False))
        self.assertEqual(sf.info(io.BytesIO(mono.wav)).channels, 1)

    def test_stereo_padding_and_resampling_keep_channels_separate(self):
        source = np.tile(np.array([[.2, -.4]], dtype=np.float32), (4800, 1))
        padded = audio.pad_silence(source, sample_rate=48000, pre_seconds=.1, post_seconds=.2)
        self.assertEqual(padded.shape, (19200, 2))
        np.testing.assert_array_equal(padded[4800:9600], source)
        for resample in (audio.resample, audio.resample_linear):
            with self.subTest(function=resample.__name__):
                result = resample(source, source_rate=48000, target_rate=24000)
                self.assertEqual(result.shape, (2400, 2))
                np.testing.assert_allclose(result[20:-20, 0], .2, atol=.001)
                np.testing.assert_allclose(result[20:-20, 1], -.4, atol=.001)
        for shape in ((0,), (0, 2)):
            empty = np.empty(shape, dtype=np.float32)
            self.assertEqual(audio.resample(empty, source_rate=48000, target_rate=24000).shape, shape)

    def test_stereo_encoder_does_not_duplicate_existing_channels(self):
        source = np.array([[.25, -.5], [.5, -.25]], dtype=np.float32)
        encoded = audio.encode_wav_stereo(source, sample_rate=48000)
        actual, _ = sf.read(io.BytesIO(encoded), dtype="float32")
        np.testing.assert_array_equal(source, actual)


class StereoRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="irodori-stereo-")
        cls.environment = patch.dict(os.environ, {"IRODORI_VOICE_DATA_DIR": cls.directory.name})
        cls.environment.start()
        from irodori_voice import paths
        paths.user_data_root.cache_clear()
        from irodori_voice.app import create_app
        from fastapi.testclient import TestClient
        from irodori_voice.settings import EngineSettings
        from irodori_voice.voices.store import VoicePresetStore
        cls.paths = paths
        cls.state = SimpleNamespace(
            settings=EngineSettings(), service=Mock(), irodori=Mock(),
            store=VoicePresetStore([]),
        )
        app = create_app()
        app.state.engine = cls.state
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.paths.user_data_root.cache_clear()
        cls.environment.stop()
        cls.directory.cleanup()

    def test_connect_mixed_rates_and_channels_preserves_stereo(self):
        stereo = np.tile(np.array([[.25, -.5]], dtype=np.float32), (4800, 1))
        mono = np.full(2400, .125, dtype=np.float32)
        waves = [base64.b64encode(audio.encode_wav(x, sample_rate=r)).decode()
                 for x, r in ((stereo, 48000), (mono, 24000))]
        response = self.client.post("/connect_waves", json=waves)
        self.assertEqual(response.status_code, 200)
        actual, rate = sf.read(io.BytesIO(response.content), dtype="float32")
        self.assertEqual((actual.shape, rate), ((9600, 2), 48000))
        np.testing.assert_array_equal(actual[:4800], stereo)
        np.testing.assert_array_equal(actual[4800:, 0], actual[4800:, 1])

    def test_api_preview_batch_and_silence_are_stereo(self):
        from irodori_voice.voicevox.schemas import AudioQuery
        from irodori_voice.routes.voicevox_compat.synthesis import _silence_response
        self.assertTrue(AudioQuery(accent_phrases=[]).outputStereo)
        source = np.zeros(4800, dtype=np.float32)
        self.state.service.synthesize.return_value = (SynthesisOutput(source, 48000, 0), False)
        payload = {"text": "こんにちは。", "voice_id": "irodori:test", "seed": 0}
        responses = [
            self.client.post("/api/synthesis", json=payload),
            self.client.post("/api/synthesis/batch", json={"lines": [payload, payload], "join_silence": .1}),
            self.client.post("/api/voices/preview-seed", json={"seed": 0, "text": "こんにちは。"}),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else "")
            self.assertEqual(sf.info(io.BytesIO(response.content)).channels, 2)
        self.assertEqual(sf.info(io.BytesIO(responses[1].content)).frames, 14400)
        silent = _silence_response(AudioQuery(accent_phrases=[]))
        self.assertEqual(sf.info(io.BytesIO(silent.body)).channels, 2)
        self.assertEqual(self.state.store.list(), [])


if __name__ == "__main__":
    unittest.main()
