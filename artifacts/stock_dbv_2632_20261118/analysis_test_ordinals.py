"""Analytic checks on the ordinal metrics; no private captures."""
import unittest
import numpy as np
from analysis_ordinals import descriptor, corr_peaks, feature


class Ordinals(unittest.TestCase):
    def test_known_coverage_distance(self):
        empty=np.zeros((2392,1080,3),np.uint8)
        half=empty.copy()
        half[1150:1240,112:326,:]=[120,120,5]
        x=descriptor(empty,18,0,0); y=descriptor(half,18,0,0)
        self.assertEqual(float(np.abs(x[0]-y[0]).mean()),.5)
        self.assertIsNone(feature(empty,x[2])[1])
        self.assertEqual(corr_peaks(x[2]),[])

    def test_horizontal_roll(self):
        a=np.zeros((2392,1080,3),np.uint8)
        a[1150:1170,112:300]=[100,100,1]
        b=a.copy(); b[1150:1240,112:540]=np.roll(b[1150:1240,112:540],33,axis=1)
        x=descriptor(a,18,0,0); y=descriptor(b,18,0,0)
        np.testing.assert_allclose(x[0],y[0],atol=1e-12)
        np.testing.assert_allclose(x[1],y[1],atol=1e-12)

    def test_neutral_blue_and_threshold_equality_excluded(self):
        a=np.zeros((2392,1080,3),np.uint8)
        for rgb in ([255,255,255],[100,115,160],[100,96,80]):
            a[1150:1240,112:540]=rgb
            self.assertFalse(descriptor(a,18,0,0)[0].any())


if __name__=="__main__":
    unittest.main()
