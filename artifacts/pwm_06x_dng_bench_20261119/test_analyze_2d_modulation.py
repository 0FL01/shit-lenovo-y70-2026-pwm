"""Synthetic unit tests for 2D spatiotemporal modulation and sinc frequency recovery."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import analyze_2d_modulation as mod


def _make_synthetic_grid(
    *,
    amp_wave: float = 0.0,
    phase_rad: float = 0.25,
    notch_center_y: float | None = None,
    notch_depth: float = 0.65,
    bg_dn: float = 28.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Create synthetic 2x2-averaged cur and flat ref arrays matching DEFAULT_B2_ROI."""
    ref = np.zeros((160, 1050), dtype=np.float64)
    y0, y1, x0, x1 = mod.DEFAULT_B2_ROI
    h, w = y1 - y0, x1 - x0
    yy, xx = np.mgrid[0:h, 0:w]
    shading = 1.0 + 0.15 * np.sin(yy / 40.0) - 0.1 * (xx / float(w))
    ref[y0:y1, x0:x1] = bg_dn * shading

    cur = np.zeros_like(ref)
    wave = 1.0 + amp_wave * np.cos(
        2.0 * math.pi * (-2.0 * yy / float(h) + 1.0 * xx / float(w)) + phase_rad
    )
    if notch_center_y is not None:
        dist = yy - (notch_center_y + 0.35 * (xx - w * 0.5))
        wave = wave * (1.0 - notch_depth * np.exp(-0.5 * (dist / 6.0) ** 2))
    cur[y0:y1, x0:x1] = 0.2 * bg_dn * shading * wave
    return cur, ref


class Analyze2DModulationTests(unittest.TestCase):
    def test_detects_diagonal_wave_and_flat_dc_suppression(self) -> None:
        cur_on, ref = _make_synthetic_grid(amp_wave=0.0)
        cur_off, _ = _make_synthetic_grid(amp_wave=0.14)

        res_on = mod.analyze_patch_2d(cur_on, ref)
        res_off = mod.analyze_patch_2d(cur_off, ref)

        self.assertLess(res_on["target_wave_amp"], 0.01)
        self.assertAlmostEqual(res_off["target_wave_amp"], 0.14, delta=0.01)
        self.assertIn(res_off["peak_2d_k"], ([2, -1], [-2, 1]))
        self.assertGreater(res_off["narrow_1d_k2_amp"], 0.12)
        self.assertLess(res_on["narrow_1d_k2_amp"], 0.01)

    def test_single_vsync_notch_distinguished_from_periodic_wave_fraction(self) -> None:
        cur_dc_with_notch, ref = _make_synthetic_grid(amp_wave=0.0, notch_center_y=45.0, notch_depth=0.65)
        res = mod.analyze_patch_2d(cur_dc_with_notch, ref)
        self.assertGreater(res["frac_lt_065"], 0.08)
        self.assertLess(res["frac_065_to_088"], 0.14)

    def test_recovers_720hz_from_sinc_exposure_sweep(self) -> None:
        true_freq = 720.0
        true_a0 = 0.155
        exps = [156.25e-6, 312.5e-6, 500e-6, 800e-6, 1000e-6, 1562.5e-6, 3125e-6]
        samples = [(t, true_a0 * abs(float(np.sinc(true_freq * t)))) for t in exps]

        fit = mod.fit_sinc_frequency(samples)
        self.assertEqual(fit["best_freq_hz"], 720)
        self.assertAlmostEqual(fit["best_a0"], true_a0, delta=0.002)
        self.assertLess(fit["candidates"]["720_hz"]["rmse"], 0.001)
        self.assertGreater(fit["candidates"]["360_hz"]["rmse"], 0.02)
        self.assertGreater(fit["candidates"]["1440_hz"]["rmse"], 0.02)
        self.assertGreater(fit["candidates"]["2160_hz"]["rmse"], 0.04)

    def test_load_bayer2x2_green_uses_only_green_sites_and_persite_black(self) -> None:
        raw = np.zeros((4, 4), dtype=np.uint16)
        raw[0::2, 0::2] = 900   # R site (ignored)
        raw[0::2, 1::2] = 74    # G1 site (black=64 -> 10)
        raw[1::2, 0::2] = 98    # G2 site (black=68 -> 30)
        raw[1::2, 1::2] = 200   # B site (ignored)
        tags = {
            256: [4],
            257: [4],
            33434: [0.0005],
            34855: [6400],
            37386: [1.64],
            33422: [0, 1, 1, 2],
            50714: [50.0, 64.0, 68.0, 120.0],
            50717: [1023],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dummy.dng"
            p.write_bytes(b"unused")
            with mock.patch.object(mod.dng_qualify, "decode_dng_bytes", return_value=(raw, tags)):
                g2, _ = mod.load_bayer2x2_green(p)
        np.testing.assert_allclose(g2, 20.0)

    def test_rejects_bad_shapes_bounds_and_zero_narrow_strip(self) -> None:
        cur, ref = _make_synthetic_grid(amp_wave=0.1)

        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur[:-1, :], ref)
        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur, ref, b2_roi=(45, 200, 930, 1010))
        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur, ref, narrow_col_slice=(940, 940))
        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur, ref, narrow_col_slice=(900, 910))

        cur_zero = cur.copy()
        cur_zero[:, 940:950] = 0.0
        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur_zero, ref, narrow_col_slice=(940, 950))

        ref_low = ref.copy()
        ref_low[50:55, 940:945] = 0.5
        with self.assertRaises(ValueError):
            mod.analyze_patch_2d(cur, ref_low)

    def test_nyquist_self_conjugate_bin_is_not_doubled(self) -> None:
        cur, ref = _make_synthetic_grid(amp_wave=0.0)
        y0, y1, x0, x1 = mod.DEFAULT_B2_ROI
        h, w = y1 - y0, x1 - x0
        gh, gw = h // mod.DEFAULT_BIN, w // mod.DEFAULT_BIN
        by = np.repeat(np.arange(gh), mod.DEFAULT_BIN)[:, None]
        bx = np.repeat(np.arange(gw), mod.DEFAULT_BIN)[None, :]
        # Exact Nyquist checkerboard modulation with cosine amplitude 0.10
        nyq = 1.0 + 0.10 * np.cos(math.pi * by + math.pi * bx)
        cur[y0:y1, x0:x1] *= nyq
        res = mod.analyze_patch_2d(cur, ref)
        self.assertAlmostEqual(res["peak_2d_amp"], 0.10, delta=0.005)


if __name__ == "__main__":
    unittest.main()
