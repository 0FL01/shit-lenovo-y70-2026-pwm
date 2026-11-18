import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw
import replay


class NightScope(unittest.TestCase):
    def test_held_out_shift_detected(self):
        red = np.zeros((1126, 850), dtype=np.uint8)
        for k in range(1, 12):
            x = 103 + 61 * k + (5 if k == 5 else 0)
            red[1072:1126, x-1:x+2] = 200
        g = replay.grid(red)
        self.assertFalse(g["passed"])
        for f in g["fits"]:
            self.assertEqual(f["px_per_div"], 61)
            self.assertEqual(f["residual_px_at_4_5_7_8"], [0,5,0,0])

    def test_single_peak_cli_is_explicitly_unresolved(self):
        width, height = 380, 101
        x = np.arange(width)
        noise = np.random.default_rng(99).integers(-3, 4, width)
        y = 75 - 40*np.exp(-.5*((x-180)/8)**2) + noise
        with tempfile.TemporaryDirectory() as tmp:
            im = Image.new("RGB", (width,height))
            ImageDraw.Draw(im).line(list(zip(x.tolist(), np.rint(y).astype(int).tolist())), fill=(230,190,40))
            path = Path(tmp)/"synthetic.png"
            im.save(path)
            c = subprocess.run([sys.executable, str(replay.ROOT/"06-tools/scope_pwm/scope_pwm.py"),
                                str(path), "--roi", "0", "0", str(width), str(height),
                                "--rgb", "230", "190", "40", "--seconds-per-div", ".005",
                                "--x-px-per-div", "61", "--volts-per-div", ".01",
                                "--y-px-per-div", "30", "--tolerance", "0"], capture_output=True, text=True)
        self.assertEqual(c.returncode, 2)
        obj = json.loads(c.stdout)
        self.assertEqual(obj["status"], "unresolved")
        for key in ("period_px", "frequency_hz"):
            self.assertNotIn(key, obj)

    def test_archived_summary(self):
        r = json.loads(Path(__file__).with_name("results.json").read_text())
        self.assertEqual(sum(x["passed"] for x in r["R034"]), 12)
        e = r["R035"]
        for row in e["estimates"]:
            n = row["n"]
            lo, hi = row["span_px"]
            self.assertEqual(lo,e["mark_intervals_px"][n][0]-e["mark_intervals_px"][0][1])
            self.assertEqual(hi,e["mark_intervals_px"][n][1]-e["mark_intervals_px"][0][0])
        s = replay.synthetic()
        self.assertEqual(s,r["R036"])
        self.assertTrue(s["passed"])


if __name__ == "__main__":
    unittest.main()
