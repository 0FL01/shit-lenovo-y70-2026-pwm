import json
import unittest
from pathlib import Path
from fractions import Fraction as F

import audit as m


class Scale(unittest.TestCase):
    def test_integral_ticks_including_negative(self):
        q = 5
        for i in range(-130, 130):
            self.assertEqual(m.area(i+1,q)-m.area(i,q), m.A[(i//q)%12])

    def test_exposure_average_independent_oracle(self):
        # Numerical midpoint integration exact on eighth-slot edges in this case.
        for phase in (F(0), F(3,8), F(-5,8)):
            y = m.profile(F(2),1,phase,21)
            for i, high in enumerate(y):
                t = phase + F(i,2)
                values = [m.A[int((t-F(1,2)+F(2*j+1,16))//1)%12] for j in range(8)]
                self.assertEqual(high, sum(values)>=12)

    def test_perfect_unblurred_scale(self):
        for p in (F(0), F(11,4), F(31,8)):
            self.assertAlmostEqual(m.fit(m.profile(3,0,p))[0],3)
        self.assertEqual(m.fit([True]*50), (None,'few_edges'))

    def test_full_period_erases_code(self):
        for p in (0,F(7,8),F(95,8)):
            self.assertFalse(any(m.profile(F(23,10),12,p)))

    def test_underresolved_and_phase_dropouts(self):
        self.assertNotIn('accepted', m.trial(F(3,4),F(0))['counts'])
        counts = m.trial(F(47,10),F(1))['counts']
        self.assertGreater(counts['accepted'],0)
        self.assertGreater(counts['shape'],0)

    def test_geometry_not_only_digest(self):
        expected = [m.A[(x//3)%12] for x in range(153)]
        for h, o, scale in ((2448,0,208),(1836,306,156)):
            model, profile = m.crop_case(h,o)
            self.assertEqual(model['modeled_us_per_px'],scale)
            self.assertEqual(profile,expected)

    def test_frozen_result_and_denominators(self):
        result = m.outcome()
        self.assertEqual(result, json.loads(Path(__file__).with_name('results.json').read_text()))
        self.assertEqual(sum(sum(c['counts'].values()) for c in result['cells']),1920)


if __name__ == '__main__':
    unittest.main()
