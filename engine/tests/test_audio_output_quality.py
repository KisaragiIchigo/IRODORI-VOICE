"""生成レートでの伸縮と最終出力のクリッピング防止を検証する。"""

from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from irodori_voice import audio
from irodori_voice.backends.base import SynthesisOutput, SynthesisParams
from irodori_voice.synthesis.pipeline import (
    LowBandPolicy, OutputFormat, SplitPolicy, synthesize_pipeline,
)
from irodori_voice.synthesis.steps.apply_speed_scale import apply_speed_scale, apply_speed_samples
from irodori_voice.voicevox.schemas import AudioQuery


class AudioOutputQualityTests(unittest.TestCase):
    def render(self, samples, *, rate=48000, scale=1.5, output=OutputFormat(stereo=False)):
        def synthesize(params):
            self.assertEqual(params.speed, 1.0)
            return SynthesisOutput(samples, rate, 42), False

        return synthesize_pipeline(
            SynthesisParams(text="音声の確認です。", voice_id="test", seed=42),
            synthesize_segment=synthesize,
            split=SplitPolicy(enabled=False),
            low_band=LowBandPolicy(enabled=False),
            speed_scale=scale,
            output=output,
        ).audio

    def test_stretch_precedes_resampling_at_native_rate(self):
        samples = np.zeros(48000, dtype=np.float32)
        calls = []

        def stretch(data, *, sample_rate, scale):
            calls.append(("stretch", sample_rate, scale))
            self.assertIs(data, samples)
            return data[:32000]

        def resample(data, *, source_rate, target_rate):
            calls.append(("resample", source_rate, target_rate))
            self.assertEqual(data.size, 32000)
            return data[::2]

        with patch("irodori_voice.synthesis.pipeline.apply_speed_samples", side_effect=stretch), \
             patch.object(audio, "resample", side_effect=resample):
            result = self.render(samples, output=OutputFormat(sample_rate=24000))
        self.assertEqual(calls, [("stretch", 48000, 1.5), ("resample", 48000, 24000)])
        self.assertEqual(result.sample_rate, 24000)
        self.assertAlmostEqual(result.duration_seconds, 2 / 3)

    def test_peak_guard_runs_after_resampling_and_preserves_stereo(self):
        converted = np.array([1.5, -1.5, .75, -.75], dtype=np.float32)
        with patch.object(audio, "resample", return_value=converted):
            result = self.render(
                np.zeros(100, dtype=np.float32), scale=1,
                output=OutputFormat(sample_rate=24000, stereo=True),
            )
        data, rate = sf.read(io.BytesIO(result.wav), dtype="float32")
        self.assertEqual(rate, 24000)
        np.testing.assert_array_equal(data[:, 0], data[:, 1])
        expected = converted * ((32767 / 32768) / 1.5)
        np.testing.assert_allclose(data[:, 0], expected, atol=1 / 32768, rtol=0)

    def test_native_output_preserves_high_frequency(self):
        time = np.arange(48000, dtype=np.float32) / 48000
        samples = .25 * np.sin(2 * np.pi * 15000 * time)
        result = self.render(samples, scale=1, output=OutputFormat(sample_rate=AudioQuery(accent_phrases=[]).outputSamplingRate))
        data, rate = sf.read(io.BytesIO(result.wav))
        self.assertEqual(rate, 48000)
        self.assertEqual(len(data), len(samples))
        self.assertAlmostEqual(np.sqrt(np.mean(data ** 2)), .25 / np.sqrt(2), places=4)

    def test_no_intermediate_pcm_clipping(self):
        samples = np.array([1.4, -1.4, .7, -.7] * 1000, dtype=np.float32)
        with patch("irodori_voice.synthesis.pipeline.apply_speed_samples", return_value=samples) as stretch:
            result = self.render(samples)
        np.testing.assert_array_equal(stretch.call_args.args[0], samples)
        data, _ = sf.read(io.BytesIO(result.wav))
        np.testing.assert_allclose(data, samples / 1.4 * (32767 / 32768), atol=1 / 32768, rtol=0)

    def test_unity_empty_and_quiet_output(self):
        for samples in [np.zeros(0, dtype=np.float32), np.zeros(480, dtype=np.float32)]:
            self.assertIs(apply_speed_samples(samples, sample_rate=48000, scale=1), samples)
        samples = np.linspace(-.5, .5, 480, dtype=np.float32)
        old = io.BytesIO()
        sf.write(old, samples, 48000, format="WAV", subtype="PCM_16")
        self.assertEqual(audio.encode_wav(samples, sample_rate=48000), old.getvalue())
        self.assertEqual(apply_speed_scale(old.getvalue(), scale=1), old.getvalue())


if __name__ == "__main__":
    unittest.main()
