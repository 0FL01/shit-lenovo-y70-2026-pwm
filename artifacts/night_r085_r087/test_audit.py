import unittest

from audit import edge_checks, run


class Tests(unittest.TestCase):
    def test_static_alias_and_controls(self):
        s = run()['stripes_max_abs']
        self.assertLess(s['same'], 1e-10)
        for key in ['delayed', 'mirrored']:
            self.assertGreater(s[key], 0.05)

    def test_window_rule_and_mixture(self):
        wins = run()['windows']
        self.assertEqual([w['candidate'] for w in wins], [None, None, 720, 720, None])
        self.assertTrue(all(w['residual720'] < 1e-10 for w in wins[:4]))
        self.assertLess(wins[0]['residual750'], wins[1]['residual750'])
        self.assertAlmostEqual(wins[2]['residual750'], 1)
        for f in (720, 750):
            self.assertAlmostEqual(wins[-1]['residual'+str(f)], 2**-0.5)

    def test_drop_and_ambiguity(self):
        e = run()['edges']
        for key in ['full', 'missing_one']:
            self.assertEqual(e[key]['candidates'], [8])
            self.assertEqual(e[key]['acf_lags'], [8])
        self.assertEqual(e['short']['candidates'], [8, 16])
        self.assertEqual(e['short']['acf_lags'], [16])
        self.assertEqual(edge_checks([0, 16, 32])['candidates'], [16])
