"""Checks that a multi-state cache cannot silently merge experimental states."""
import unittest
import numpy as np
from reanalyse_cached_stages import reanalyse


class CachedStageTests(unittest.TestCase):
    def test_windows_preserve_two_distinct_stationary_periods(self):
        rows, frames = 1488, 60
        profile_a = 40 + np.sin(2 * np.pi * np.arange(rows) / 93)
        profile_b = 40 + np.sin(2 * np.pi * np.arange(rows) / 31)
        profiles = np.concatenate([np.tile(profile_a, (frames, 1)),
                                   np.tile(profile_b, (frames, 1))])
        pts = np.arange(frames * 2) / 30
        stages = [{"label": "stock", "window_s": [0, 2], "frames": 60},
                  {"label": "candidate", "window_s": [2, 4], "frames": 60}]
        report, spectra = reanalyse(profiles, pts, stages)
        self.assertAlmostEqual(report["stages"][0]["peaks"][0]["period_rows"], 93, delta=1)
        self.assertAlmostEqual(report["stages"][1]["peaks"][0]["period_rows"], 31, delta=0.2)
        self.assertEqual(len(spectra["stage_00_pts_s"]), 60)
        self.assertGreaterEqual(spectra["stage_01_pts_s"].min(), 2)
        self.assertIsNone(report["pwm_hz"])

    def test_mismatched_timestamp_origin_is_not_silently_accepted(self):
        profiles = np.ones((90, 64))
        pts = np.arange(90) / 30 + 0.1
        with self.assertRaisesRegex(ValueError, "Frame count differs"):
            reanalyse(profiles, pts, [{"label": "stock", "window_s": [0, 2], "frames": 60}])


if __name__ == "__main__":
    unittest.main()
