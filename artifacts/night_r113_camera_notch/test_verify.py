"""Synthetic fixtures only. Nothing here is a camera frame or a device result."""
import math
import unittest

import verify as v


def fixture(f, err=.002, amp=.2):
    times = {"S":156., "M":468., "L":676.}
    blocks = []
    for j, order in enumerate(v.ORDERS*2):
        samples = []
        for label in order:
            t = times[label]
            a = amp*v.response(f*t*1e-6)
            samples.append({"actual_time_us":[t-.5,t+.5], "amplitude":[max(0,a-err),a+err]})
        blocks.append({"id":str(j), "order":order, "samples":samples})
    return {"units":"black_corrected_linear_fractional_amplitude",
            "frequency_relative_tolerance":.01, "minimum_fractional_contrast":.002,
            "gates":dict.fromkeys(v.GATES, True), "blocks":blocks}


class Test(unittest.TestCase):
    def test_three_components(self):
        for f in v.FREQ:
            with self.subTest(f=f):
                self.assertEqual(v.verify(fixture(f))["candidate_hz"], f)

    def test_uniform_exposure_grid_alias(self):
        # 52-us grid: alias and 2160 have identical normalized absolute sinc ratios.
        f = 1e6/52 - 2160
        d = fixture(f, err=.0002)
        d["minimum_fractional_contrast"] = .0001
        self.assertEqual(v.verify(d)["candidate_hz"], 2160)
        for n in (1,3,9,13,22):
            self.assertAlmostEqual(v.response(f*n*52e-6)*f, v.response(2160*n*52e-6)*2160)

    def test_720_fundamental_2160_line(self):
        # Explicit positive light waveform with fundamental 720 and third harmonic 2160.
        L = lambda t: 1+.28*math.cos(2*math.pi*720*t)+.12*math.cos(2*math.pi*2160*t)
        self.assertNotAlmostEqual(L(0), L(1/2160))
        self.assertAlmostEqual(L(0), L(1/720))
        d = fixture(3*720, amp=.12)
        self.assertEqual(v.verify(d)["status"], "CONDITIONAL_COMPONENT_MATCH")

    def test_noisy_or_null(self):
        for d in (fixture(1440, err=.15), fixture(720, amp=0), fixture(900, err=.0002)):
            self.assertEqual(v.verify(d)["status"], "HOLD")

    def test_bad_orders_frames_and_units(self):
        def run(fn):
            d = fixture(2160)
            fn(d)
            self.assertEqual(v.verify(d)["status"], "HOLD")
        run(lambda d: d.update(units="raw_DN"))
        run(lambda d: d["gates"].update(capture_result_per_frame=False))
        run(lambda d: d.update(blocks=d["blocks"][:2]))
        run(lambda d: d["blocks"][3].update(id="0"))
        run(lambda d: d["blocks"][0]["samples"][3].update(amplitude=[.01,.02]))
        run(lambda d: d["blocks"][0]["samples"][1].update(actual_time_us=[.468,.469]))
        run(lambda d: d["blocks"][0]["samples"][1].update(amplitude=[0,float("nan")]))
        run(lambda d: d["blocks"][0]["samples"].reverse())

    def test_floor_censored_notch(self):
        d = fixture(2160)
        for b in d["blocks"]:
            b["samples"][b["order"].index("M")]["amplitude"] = [0,.009]
        self.assertEqual(v.verify(d)["candidate_hz"], 2160)

    def test_mixture_not_forced_to_nearest(self):
        d = fixture(720)
        other = fixture(2160)
        for b, c in zip(d["blocks"], other["blocks"]):
            for s, t in zip(b["samples"], c["samples"]):
                s["amplitude"] = [(x+y)/2 for x,y in zip(s["amplitude"], t["amplitude"])]
        self.assertEqual(v.verify(d)["status"], "HOLD")

    def test_envelope_covers_interior_null(self):
        t = (449, 481)
        lo, hi = v.envelope(2160,.01,t)
        self.assertEqual(lo,0)
        for i in range(101):
            for j in range(101):
                x = 2160*(.99+j/5000)*(t[0]+(t[1]-t[0])*i/100)*1e-6
                self.assertLessEqual(lo, v.response(x))
                self.assertLessEqual(v.response(x), hi)


if __name__ == "__main__":
    unittest.main()
