from itertools import product
import json
import os
from pathlib import Path
import unittest

import numpy as np
from replay import centres, dvalues, group, hist, run, sample, signs, summary


class Fixture(unittest.TestCase):
    def test_discrete_cdf_equals_sorted_distance(self):
        # Exhaustive two-column heights 0..2, including ties and empty masks.
        for aa,bb in product(product(range(3),repeat=2), repeat=2):
            a,b=(np.arange(2)[:,None]<pair for pair in (aa,bb))
            self.assertEqual(int(abs(hist(a)-hist(b)).sum()),
                             sum(abs(u-v) for u,v in zip(sorted(aa),sorted(bb))))

    def test_patches_fixed_geometry(self):
        x,y=centres([0,0,4,0,0,4])
        self.assertEqual((x[0,1],y[0,1]),(6,2))
        g=np.zeros((34,34),dtype=np.uint8)
        for row in range(8):
            for col in (0,2,4,6):
                xx,yy=x[row,col],y[row,col]
                g[yy-1:yy+2,xx-1:xx+2]=200
                g[yy,xx]=0 # perturbation leaves 3x3 median unchanged
        expected=np.tile([1,-1,1,-1,1,-1,1,-1],(8,1))
        np.testing.assert_array_equal(signs(sample(g,x,y)),expected)
        self.assertRaises(ValueError,sample,g,x-5,y)

    def test_tie_and_nonadjacency(self):
        np.testing.assert_array_equal(signs(np.zeros((8,8)))[2],[-1]*4+[1]*4)
        self.assertIsNone(group(1,8))
        self.assertEqual(group(1,5),'same')
        self.assertEqual(group(1,2),'cross')
        a={i:[np.array([0])]*3 for i in range(3)}
        self.assertEqual(len(dvalues(a,1,1)),3)
        self.assertEqual(len(dvalues(a,1,2)),9)
        self.assertFalse(summary(a,range(3))['separated'])  # equality fails strictly

    @unittest.skipUnless(all(os.environ.get(x) for x in ('R12B','R7','SHAM')),'private archive roots not supplied')
    def test_archive(self):
        data=run(*(Path(os.environ[x]) for x in ('R12B','R7','SHAM')))
        self.assertEqual(data,json.loads(Path(__file__).with_name('result.json').read_bytes()))


if __name__=='__main__':
    unittest.main()
