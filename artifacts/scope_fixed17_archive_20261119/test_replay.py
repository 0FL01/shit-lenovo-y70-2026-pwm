import unittest
import numpy as np
from replay import features

class FeatureTests(unittest.TestCase):
    def test_offset_and_phase(self):
        x = np.arange(714)
        for phase in (0,.73):
            a,b,c=features(120+7*np.cos(2*np.pi*x/17+phase))
            self.assertAlmostEqual(a,7)
            self.assertAlmostEqual(b,7)
            self.assertAlmostEqual(c,1)

    def test_local_contrast_can_cancel(self):
        x = np.arange(17)
        s = np.tile(np.r_[np.cos(2*np.pi*x/17),-np.cos(2*np.pi*x/17)],21)
        a,b,c=features(60+15*s)
        self.assertAlmostEqual(a,0)
        self.assertAlmostEqual(b,15)
        self.assertAlmostEqual(c,0)

    def test_no_variation(self):
        a,b,c=features(np.full(714,200))
        self.assertAlmostEqual(a,0)
        self.assertAlmostEqual(b,0)
        self.assertIsNone(c)

    def test_wrong_width(self):
        with self.assertRaises(ValueError):
            features(np.zeros(720))

if __name__=="__main__":
    unittest.main()
