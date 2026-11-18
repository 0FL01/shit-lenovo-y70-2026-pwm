import json
from pathlib import Path
import unittest

import numpy as np
import replay as r
import return_scale as ret


class Geometry(unittest.TestCase):
    def test_d4_semantics(self):
        a = r.code('B')
        flipped = np.roll(np.rot90(np.fliplr(a)), (2, 5), (0,1))
        q = r.rank(flipped, a)
        self.assertEqual((q['correct'], q['ties'], q['identity_wins']), (64,1,False))

    def test_symmetric_control(self):
        a = np.indices((8,8)).sum(0) % 2
        self.assertEqual(r.rank(a, a)['ties'], 256)
        self.assertEqual(r.rank(a*0, a*0)['ties'],512)

    def test_partition(self):
        even = {(x, y) for x, y, z in r.corners(r.code('A'), 0)}
        odd = {(x, y) for x, y, z in r.corners(r.code('B'), 1)}
        self.assertEqual((len(even), len(odd)),(12,11))
        self.assertFalse(even & odd or even.intersection(ret.QUAD))

    def test_known_perspective(self):
        h = np.array([[12.,-1.,2.], [1.,12.,-1.], [.003,-.004,1.]])
        m = [dict(src=[x,y],xy=r.project(h,(x,y)),accepted=True)
             for x,y,z in r.corners(r.code('A'),0)]
        guess = r.fit(m)
        for x,y,z in r.corners(r.code('B'),1):
            np.testing.assert_allclose(r.project(guess,(x,y)),r.project(h,(x,y)),atol=1e-9)

    def test_fail_closed(self):
        m = [dict(src=[i,0],xy=r.ORIGIN+[i,0],accepted=True) for i in range(7)]
        with self.assertRaises(ValueError): r.fit(m)
        self.assertIsNone(r.band_pitch(m,(1,2))['median_px'])
        m = [dict(src=s,xy=s,accepted=False) for s in ret.QUAD]
        self.assertFalse(ret.measure(m)['complete'])

    def test_no_corners_on_flat(self):
        self.assertEqual(list(r.corners(np.zeros((8,8)),0)),[])
        q = r.locate(np.zeros((1200,1080)),3,2,np.array([[1,0],[0,1]]))
        self.assertFalse(q['accepted'])

    def test_shift_invariance_of_transfer(self):
        # Same ROI shift of all four corners is not a change of local scale.
        m = [dict(src=s,xy=np.array(s)*11.5+[20,39],accepted=True) for s in ret.QUAD]
        q = ret.measure(m)
        self.assertEqual(q['anchored_copy_error_px'],0)
        self.assertEqual(q['pitches_px'],[11.5,11.5])

    def test_published_correspondences(self):
        p = Path(__file__).parent
        raw = json.loads((p/'result.json').read_text())
        self.assertEqual(raw['r025'],r.r025())
        for v in raw['test'].values():
            self.assertEqual((v['eligible'],v['accepted'],v['bottom']['pairs']),(11,11,0))
            self.assertTrue(v['all_under_2px'])
        a,b = json.loads((p/'return_scale.json').read_text()).values()
        self.assertLess(a['relative_change'],0)
        self.assertGreater(b['relative_change'],0)
        for slot in (a,b):
            self.assertEqual(ret.measure(slot['landmarks'])['anchored_copy_error_px'],
                             slot['anchored_copy_error_px'])


if __name__ == '__main__':
    unittest.main()
