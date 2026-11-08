"""Regression tests for optical-analysis failure modes, using synthetic data only."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from optical_spectrum import analyze_profiles, main


def sinusoid(frames: int, rows: int, frequency: float, phase: np.ndarray) -> np.ndarray:
    return 40.0 + np.sin(2 * np.pi * frequency * np.arange(rows)[None, :] + phase[:, None])


class OpticalSpectrumTests(unittest.TestCase):
    def test_stationary_stripes_survive_while_old_analysis_erases_them(self):
        frame_count, rows, frequency = 75, 512, 1 / 32
        profiles = sinusoid(frame_count, rows, frequency, np.zeros(frame_count))
        result = analyze_profiles(profiles, frequencies=[frequency])
        legacy_input = profiles - profiles.mean(axis=0)
        legacy = analyze_profiles(legacy_input, frequencies=[frequency])
        self.assertGreater(result["total_rms_amplitude"][0], 0.99)
        self.assertAlmostEqual(
            result["coherent_amplitude"][0], result["total_rms_amplitude"][0], places=12
        )
        self.assertLess(result["incoherent_rms_amplitude"][0], 1e-12)
        self.assertLess(legacy["total_rms_amplitude"][0], 1e-12)

    def test_phase_rotating_stripes_are_retained_as_incoherent_power(self):
        frame_count, rows, frequency = 60, 512, 1 / 32
        phase = 2 * np.pi * np.arange(frame_count) / frame_count
        result = analyze_profiles(sinusoid(frame_count, rows, frequency, phase), frequencies=[frequency])
        self.assertGreater(result["total_rms_amplitude"][0], 0.99)
        self.assertLess(result["coherent_amplitude"][0], 1e-12)
        self.assertAlmostEqual(
            result["total_power"][0], result["incoherent_power"][0], places=12
        )

    def test_slow_drift_does_not_falsely_reduce_total_stripe_amplitude(self):
        frame_count, rows, frequency = 75, 512, 1 / 32
        phase = 2 * np.pi * 0.1 * np.arange(frame_count) / 30.0
        profiles = sinusoid(frame_count, rows, frequency, phase)
        result = analyze_profiles(profiles, frequencies=[frequency])
        legacy = analyze_profiles(profiles - profiles.mean(axis=0), frequencies=[frequency])
        self.assertGreater(result["total_rms_amplitude"][0], 0.99)
        expected_ratio = np.sqrt(1.0 - abs(np.exp(1j * phase).mean()) ** 2)
        observed_ratio = legacy["total_rms_amplitude"][0] / result["total_rms_amplitude"][0]
        self.assertAlmostEqual(observed_ratio, expected_ratio, delta=0.001)
        self.assertAlmostEqual(observed_ratio, 0.435202, delta=0.001)
        self.assertAlmostEqual(
            legacy["total_rms_amplitude"][0], result["incoherent_rms_amplitude"][0], places=12
        )

    def test_period_93_to_31_moves_peak_in_full_spectrum(self):
        frame_count, rows = 12, 1488
        baseline = analyze_profiles(sinusoid(frame_count, rows, 1 / 93, np.zeros(frame_count)))
        changed = analyze_profiles(sinusoid(frame_count, rows, 1 / 31, np.zeros(frame_count)))
        old_peak = baseline["peaks"][0]
        new_peak = changed["peaks"][0]
        self.assertAlmostEqual(old_peak["frequency_cycles_per_row"], 1 / 93, delta=1 / baseline["n_fft"])
        self.assertAlmostEqual(new_peak["frequency_cycles_per_row"], 1 / 31, delta=1 / changed["n_fft"])
        self.assertAlmostEqual(
            new_peak["frequency_cycles_per_row"] / old_peak["frequency_cycles_per_row"], 3.0, delta=0.02
        )
        self.assertGreater(new_peak["total_rms_amplitude"], 0.98)
        self.assertFalse(new_peak["at_frequency_boundary"])
        old_component_in_new = analyze_profiles(
            sinusoid(frame_count, rows, 1 / 31, np.zeros(frame_count)), frequencies=[1 / 93]
        )
        self.assertLess(old_component_in_new["total_rms_amplitude"][0], 0.01)

    def test_multiple_peaks_preserve_fundamental_and_third_harmonic(self):
        rows, frames = 1488, 8
        x = np.arange(rows)
        profile = 50 + np.sin(2 * np.pi * x / 93) + 0.6 * np.sin(2 * np.pi * x / 31)
        result = analyze_profiles(np.tile(profile, (frames, 1)), peak_count=4)
        strongest = [peak["frequency_cycles_per_row"] for peak in result["peaks"][:2]]
        self.assertTrue(any(abs(f - 1 / 93) < 1 / result["n_fft"] for f in strongest))
        self.assertTrue(any(abs(f - 1 / 31) < 1 / result["n_fft"] for f in strongest))

    def test_power_partition_raw_mean_and_input_preservation(self):
        rng = np.random.default_rng(20261107)
        frames, rows = 75, 500
        x = np.linspace(-1.0, 1.0, rows)
        phase = 2 * np.pi * np.arange(frames) / frames
        profiles = (
            37.0 + 2.0 * x + 0.4 * x**2
            + 2.0 * np.sin(2 * np.pi * np.arange(rows)[None, :] / 31)
            + sinusoid(frames, rows, 1 / 93, phase) - 40.0
            + rng.normal(0, 0.1, (frames, rows))
        )
        original = profiles.copy()
        result = analyze_profiles(profiles, frequencies=np.linspace(0, 0.5, 257))
        np.testing.assert_allclose(
            result["total_power"], result["coherent_power"] + result["incoherent_power"],
            rtol=2e-13, atol=1e-25,
        )
        np.testing.assert_array_equal(profiles, original)
        np.testing.assert_allclose(result["raw_mean_per_frame"], profiles.mean(axis=1), rtol=0, atol=0)
        self.assertAlmostEqual(result["raw_mean"], profiles.mean(), places=12)

    def test_explicit_grid_and_fft_agree(self):
        rng = np.random.default_rng(7)
        profiles = rng.normal(size=(5, 128))
        fft = analyze_profiles(profiles, n_fft=512)
        direct = analyze_profiles(profiles, frequencies=fft["frequencies_cycles_per_row"])
        for key in ("total_power", "coherent_power", "incoherent_power"):
            np.testing.assert_allclose(fft[key], direct[key], rtol=2e-12, atol=1e-15)

    def test_dc_mean_is_retained_separately(self):
        profiles = np.full((4, 64), 39.5)
        result = analyze_profiles(profiles)
        self.assertEqual(result["raw_mean"], 39.5)
        self.assertLess(float(result["total_rms_amplitude"].max()), 1e-12)
        no_detrend = analyze_profiles(profiles, detrend_degree=None, window="rectangular", n_fft=64)
        self.assertAlmostEqual(no_detrend["total_rms_amplitude"][0], 39.5, places=12)

    def test_cli_npz_round_trip_with_restricted_frequency_range(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "profiles.npz"
            output = Path(directory) / "spectrum.json"
            np.savez(source, profiles=sinusoid(3, 128, 1 / 32, np.zeros(3)))
            self.assertEqual(main([
                str(source), "--output", str(output),
                "--min-frequency", "0.01", "--max-frequency", "0.1", "--peaks", "3",
            ]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["units"]["frequency"], "cycles_per_camera_row")
            self.assertGreater(result["peaks"][0]["total_rms_amplitude"], 0.99)
            self.assertTrue(all(0.01 <= f <= 0.1 for f in result["frequencies_cycles_per_row"]))
            self.assertNotIn("pwm_hz", result)

    def test_invalid_input_and_empty_frequency_interval_are_rejected(self):
        with self.assertRaises(ValueError):
            analyze_profiles(np.ones(64))
        with self.assertRaises(ValueError):
            analyze_profiles(np.full((2, 64), np.nan))
        with self.assertRaises(ValueError):
            analyze_profiles(np.ones((2, 64)), frequencies=[0.2, 0.1])
        with self.assertRaises(ValueError):
            analyze_profiles(np.ones((2, 64)), frequencies=[0.6])
        with self.assertRaises(ValueError):
            analyze_profiles(np.ones((2, 64)), frequency_min=0.15, frequency_max=0.15)


if __name__ == "__main__":
    unittest.main()
