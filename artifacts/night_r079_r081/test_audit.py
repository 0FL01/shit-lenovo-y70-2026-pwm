import unittest

import audit


class Archive(unittest.TestCase):
    def test_primary(self):
        r = audit.run()
        grid = r['R079_adjacent_transitions_only']
        self.assertEqual(grid['18,0,0']['strict_wins_over_controls'], 8)
        self.assertTrue(all(v['comparisons'] == 40 and v['min_boundary_minus_max_control'] < 0 for v in grid.values()))
        self.assertEqual(r['R080_locked_round']['minimum_off_or_return_minus_max_on'], 0.433831)
        self.assertEqual(r['R081_model_only']['133']['sRGB_decoded_linear'], 0.234551)

    def test_cannot_complete_missing_pair_by_duplication(self):
        data = audit.rows('stock_dbv_r7_ordinal_20261118/results/ordinal_pairs.csv')
        for bad in (data[:-1], data[:-1]+data[:1]):
            with self.assertRaises(ValueError):
                audit.boundary(bad)

    def test_phase_and_exposure(self):
        frames = audit.rows('extra_dim_round2_raster_audit_20261118/derived/frames.csv')
        obs = audit.load('stock_extra_dim_locked_20261118/observations.json')
        for bad in (frames[1:], [dict(frames[0], ISO='5587')] + frames[1:]):
            with self.assertRaises(ValueError):
                audit.extra_dim(bad, obs)


if __name__ == '__main__':
    unittest.main()
