import cmath
import math
import unittest

from models import A, B, TRAINS, amp, result, rms, rows


class Synthetic(unittest.TestCase):
    def test_numeric_fourier_independent(self):
        # Midpoint DFT of directly rasterized piecewise-constant light curves.
        count = 6000
        for weights in TRAINS:
            k = len(weights)
            for duty in (.10, .50, .90, .99):
                sig = [weights[(k*i)//count] if (k*(i+.5)/count)%1 < duty else 0.
                       for i in range(count)]
                for n in (1, 2, 3):
                    got = 2*abs(sum(y*cmath.exp(-2j*math.pi*n*(i+.5)/count)
                                    for i,y in enumerate(sig)))/count
                    self.assertAlmostEqual(got, amp(n,duty,weights), places=6)

    def test_duty_sweep(self):
        scans = result()['R083']
        self.assertEqual(scans[0]['percent_strictly_above_fundamental'], {2: [], 3: []})
        for s, n in zip(scans[1:], (2, 3)):
            lo, hi, count = s['percent_strictly_above_fundamental'][n]
            self.assertEqual(lo, 1)
            self.assertEqual(count, hi)
            self.assertLess(hi, 99)
        self.assertEqual(scans[1]['percent_strictly_above_fundamental'][3], [])
        self.assertEqual(scans[2]['percent_strictly_above_fundamental'][2], [])

    def test_pair_is_distinct(self):
        a, b = (rows(t,11520) for t in (A,B))
        self.assertAlmostEqual(rms(a,b), .22)
        self.assertTrue(all(0 <= y <= 1 for y in a+b))

    def test_exposure_by_quadrature(self):
        for terms in (A,B):
            obs = rows(terms,2880,.0001)
            for i in range(4):
                ys = [.5+sum(a*math.cos(2*math.pi*f*(i/2880+(.5+j-500)*1e-7))
                              for f,a in terms) for j in range(1000)]
                self.assertAlmostEqual(obs[i],sum(ys)/1000,places=7)

    def test_weak_line_without_alias(self):
        s = result()['R084_weak_fundamental']
        self.assertTrue(s['similar'])
        self.assertAlmostEqual(s['rms'], .015/math.sqrt(2))
        self.assertEqual(s['720_projection'], [.015, 0])

    def test_alias_controls(self):
        cases = result()['R084']
        self.assertEqual([c['similar'] for c in cases], [True, True, False, False])
        self.assertLess(rms(rows(A,2880),rows(B,2880)),1e-12)


if __name__ == '__main__':
    unittest.main()
