"""Synthetic and frozen archive checks; no private files, camera, adb or network."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import audit


class TestAudit(unittest.TestCase):
    def test_shift_invariance_and_fractional_discrimination(self):
        p = 93.4
        t = 2*np.pi*audit.U/p
        for shift in [.2,2.9]:
            v = 41 + 4*np.cos(t+shift) - 3*np.cos(2*(t+shift)) + .6*np.cos(audit.R*t+.7)
            s = audit.stats(v[None],p)
            self.assertEqual(s["frac_over_A1"], .15)
            self.assertEqual(s["Ah_over_A1"][1], .75)
            self.assertEqual(s["cos_phase_2_3_4"][0], -1)

    def test_uninjected_with_integer_seventh_line(self):
        p = 93.4
        t = 2*np.pi*audit.U/p
        s = audit.stats((6 + np.cos(t) + .6*np.cos(7*t))[None],p)
        self.assertEqual(s["frac_over_A1"], 0)
        self.assertEqual(s["Ah_over_A1"][6], .6)

    def test_same_frequency_different_polarity_control(self):
        s = audit.synthetic(93.4)["sigmoid"]
        self.assertEqual(s["-13"]["cos_phase_2_3_4"][0], 1)
        self.assertEqual(s["13"]["cos_phase_2_3_4"][0], -1)
        self.assertAlmostEqual(s["-13"]["Ah_over_A1"][1], .852, places=3)
        self.assertAlmostEqual(s["13"]["Ah_over_A1"][2], .653, places=3)

    def test_conditional_rectangular_prediction_on_forward_model(self):
        p = 93.4
        q = []
        for d in [96/720,704/720,96/720]:
            phase = 2*np.pi*audit.U/p
            # Common linear transfer H_k and arbitrary gain per brightness.
            y = d + (2+d)*sum(np.sin(np.pi*k*d)/k * np.exp(-.05*k*k) * np.cos(k*phase)
                              for k in audit.H)
            c = abs(audit.coef(y[None],p,[*audit.H,audit.R])[0])
            q.append(c[:10]/c[0])
        result = audit.rectangle_double_ratios(q)
        self.assertEqual(result["predicted"], result["observed"])

    def test_public_input_schema_and_golden_output(self):
        with np.load(audit.HERE/"strip_sums.npz",allow_pickle=False) as f:
            self.assertEqual(f.files, ["strip_sums"])
            a = audit.validate(f["strip_sums"])
        expected = json.loads((audit.HERE/"expected.json").read_text())
        self.assertEqual(audit.analyse(a), expected)
        with self.assertRaises(ValueError):
            audit.validate(a.astype(float))
        stats = expected["conditional_off_time_model"]
        self.assertTrue(all(x > 1 for x in stats["predicted"]))
        self.assertTrue(all(x < 1 for x in stats["observed"]))

    def test_reject_wrong_archive_before_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"wrong.mp4"
            path.write_bytes(b"not the input archive")
            with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
                audit.extract(path)


if __name__ == "__main__":
    unittest.main()
