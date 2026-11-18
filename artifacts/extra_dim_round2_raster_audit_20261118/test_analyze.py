import unittest
import numpy as np
from analyze import grid, profile

class RasterTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(811)
        self.img=rng.integers(0,200,(429,550,3))

    def test_phase_permutation(self):
        a=self.img.copy()
        a[276:322,51:508]=np.roll(a[276:322,51:508],37,axis=1)
        np.testing.assert_array_equal(profile(a,"R",.96)[0],profile(self.img,"R",.96)[0])

    def test_global_strict_monotone(self):
        a=190*(self.img/200)**1.8
        np.testing.assert_array_equal(profile(a,"R",.96)[0],profile(self.img,"R",.96)[0])

    def test_saturated_or_flat_reference(self):
        for v in (255,50):
            a=self.img.copy()
            a[60:135,180:256]=v
            self.assertIsNone(profile(a,"R",.96)[0])

    def test_known_grid_translation(self):
        red=self.img[:,:,0]
        ref=red[65:125,183:250]
        result=grid(np.roll(red,(2,-1),axis=(0,1)),ref)
        self.assertEqual(result[3:],[ -1,2,1.0])

    def test_step(self):
        a=self.img.copy();b=a.copy()
        a[276:322,51:508]=0;b[276:322,51:508]=250
        self.assertEqual(float(abs(profile(a,"R",.96)[0]-profile(b,"R",.96)[0]).mean()),1.)

if __name__=="__main__":
    unittest.main()
