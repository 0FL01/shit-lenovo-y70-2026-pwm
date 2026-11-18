"""Deterministic oscilloscope screenshots, not phone measurements."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw
from scope_pwm import Calibration, Unresolved, measure


RGB = (240, 210, 45)
W, H = 380, 101
ROI = (10, 5, W - 10, H - 5)
CAL = Calibration(.0005, 40, .2, 20, "positive", 90, True)


def draw(f, seed_grid=True):
    im = Image.new("RGB", (W, H))
    pen = ImageDraw.Draw(im)
    if seed_grid:
        for x in range(0, W, 40):
            pen.line((x, 0, x, H), fill=(60, 60, 60))
        for y in range(0, H, 20):
            pen.line((0, y, W, y), fill=(60, 60, 60))
    pen.line([(x, round(f(x))) for x in range(W)], fill=RGB, width=1)
    return im


def square(x):
    return 30 if x % 40 < 10 else 70


def run(im, cal=CAL):
    return measure(im, ROI, RGB, 8, cal)


class TestScope(unittest.TestCase):
    def test_calibrated_square(self):
        result = run(draw(square))
        self.assertAlmostEqual(result["frequency_hz"], 2000)
        self.assertAlmostEqual(result["optical_high_duty_pct"], 25, delta=1)
        self.assertAlmostEqual(result["trace_vpp_p02_p98"], .4)
        self.assertAlmostEqual(result["dark_referenced_max_v"], .6)
        self.assertAlmostEqual(result["dark_referenced_min_v"], .2)
        self.assertAlmostEqual(result["percent_modulation"], 50)
        self.assertGreaterEqual(result["complete_periods"], 7)

    def test_amplitude_is_not_frequency(self):
        a, b = run(draw(square)), run(draw(lambda x: 50 + (square(x) - 50) / 2))
        self.assertEqual(a["frequency_hz"], b["frequency_hz"])
        self.assertAlmostEqual(a["trace_vpp_p02_p98"], 2 * b["trace_vpp_p02_p98"])
        c = run(draw(square), replace(CAL, seconds_per_div=.001))
        self.assertAlmostEqual(c["frequency_hz"], 1000)
        self.assertEqual(a["trace_vpp_p02_p98"], c["trace_vpp_p02_p98"])

    def test_polarity_and_baseline(self):
        im = draw(lambda x: 100 - square(x))
        r = run(im, replace(CAL, polarity="negative", dark_y=10))
        self.assertAlmostEqual(r["optical_high_duty_pct"], 25, delta=1)
        self.assertAlmostEqual(r["percent_modulation"], 50)
        for cal in (replace(CAL, dark_y=None), replace(CAL, linear_dc_unclipped=False),
                    replace(CAL, polarity="unknown"), replace(CAL, dark_y=50)):
            self.assertIsNone(run(draw(square), cal)["percent_modulation"])
        self.assertIsNone(run(im, replace(CAL, polarity="unknown"))["optical_high_duty_pct"])

    def test_sine_is_not_pwm(self):
        r = run(draw(lambda x: 50 - 20 * math.sin(2 * math.pi * x / 48)))
        self.assertAlmostEqual(r["frequency_hz"], 1 / .0006, delta=8)
        self.assertFalse(r["resolved_two_level_shape"])
        self.assertIsNone(r["optical_high_duty_pct"])

    def test_triangle_on_flat_baseline_is_not_pwm(self):
        r = run(draw(lambda x: 70 - 5 * max(0, 8 - abs(x % 80 - 40))))
        self.assertFalse(r["resolved_two_level_shape"])
        self.assertIsNone(r["optical_high_duty_pct"])

    def test_duty_changes(self):
        r = run(draw(lambda x: 30 if x % 40 < (10 if x // 40 % 2 else 20) else 70))
        self.assertAlmostEqual(r["frequency_hz"], 2000)
        self.assertEqual(r["frequency_kind"], "rising_edge_repetition_rate")
        self.assertIsNone(r["waveform_fundamental_hz"])  # actual 80 px pattern: 1000 Hz
        self.assertTrue(r["cycle_variation_detected"])
        self.assertTrue(any("Cycles differ" in msg for msg in r["warnings"]))
        self.assertIsNone(r["optical_high_duty_pct"])

    def test_trailing_and_leading_flat_burst(self):
        for f in (lambda x: square(x) if x < 170 else 70,
                  lambda x: square(x) if x >= 170 else 30):
            with self.assertRaisesRegex(Unresolved, "burst or pause"):
                run(draw(f))

    def test_pulse_amplitude_alternation(self):
        r = run(draw(lambda x: (30 if x // 40 % 2 else 40) if x % 40 < 10 else 70))
        self.assertTrue(r["cycle_variation_detected"])
        self.assertIsNone(r["waveform_fundamental_hz"])

    def test_extrema_outside_quantiles_and_dark(self):
        for f in (lambda x: 94 if 95 <= x < 99 else square(x),
                  lambda x: 10 if 42 <= x < 47 else square(x)):
            r = run(draw(f))
            self.assertTrue(r["out_of_quantile_excursion"])
            self.assertIsNone(r["percent_modulation"])
        self.assertTrue(any("below dark" in w for w in
                            run(draw(lambda x: 94 if 95 <= x < 99 else square(x)))["warnings"]))

    def test_clipped_sine_raster_duty_is_not_optical(self):
        im = draw(lambda x: 50 - max(-20, min(20, 160 * math.sin(x * 2 * math.pi / 40))))
        r = run(im, replace(CAL, linear_dc_unclipped=False))
        self.assertAlmostEqual(r["raster_upper_duty_pct"], 50)
        self.assertIsNone(r["optical_high_duty_pct"])
        self.assertIsNone(r["percent_modulation"])

    def test_filled_band_is_not_a_trace(self):
        im = Image.new("RGB", (W, H))
        pen = ImageDraw.Draw(im)
        for x in range(W):
            pen.line((x, 20, x, 45 if x % 40 < 10 else 80), fill=RGB)
        with self.assertRaisesRegex(Unresolved, "filled or ambiguous band"):
            run(im)

    def test_bad_trace_rejected(self):
        gap = draw(square)
        ImageDraw.Draw(gap).line((100, 0, 100, H), fill=(0, 0, 0))
        extra = draw(square)
        ImageDraw.Draw(extra).line((30, 10, 120, 10), fill=RGB)
        images = [gap, extra, draw(lambda x: 50), draw(lambda x: 5 if x % 40 < 10 else 70),
                  draw(lambda x: 30 if x % 8 < 4 else 70),
                  draw(lambda x: 30 if x % 200 < 60 else 70),
                  draw(lambda x: square(x) if x < 180 else square(x // 2))]
        for i, im in enumerate(images):
            with self.subTest(i=i), self.assertRaises(Unresolved):
                run(im)

    def test_bad_calibration(self):
        for cal in (replace(CAL, seconds_per_div=0), replace(CAL, volts_per_div=float("nan")),
                    replace(CAL, x_px_per_div=-5), replace(CAL, dark_y=H),
                    replace(CAL, seconds_per_div=5e-324, x_px_per_div=1e10),
                    replace(CAL, volts_per_div=1e308, y_px_per_div=1e-308)):
            with self.assertRaises(Unresolved):
                run(draw(square), cal)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "scope.png"
            draw(square).save(p)
            args = [sys.executable, str(Path(__file__).with_name("scope_pwm.py")), str(p),
                    "--roi", *map(str, ROI), "--rgb", *map(str, RGB),
                    "--seconds-per-div", ".0005", "--x-px-per-div", "40",
                    "--volts-per-div", ".2", "--y-px-per-div", "20", "--polarity", "positive"]
            proc = subprocess.run(args, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(proc.stdout)["frequency_hz"], 2000)
            self.assertIsNone(json.loads(proc.stdout)["percent_modulation"])
            draw(lambda x: 50).save(p)
            bad = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(json.loads(bad.stdout)["status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
