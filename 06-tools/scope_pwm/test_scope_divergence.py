import unittest
import numpy as np
from scope_divergence import profiles, descriptor, distances


class TestMetric(unittest.TestCase):
    def test_roll(self):
        p=np.random.default_rng(1).random((2,400))
        np.testing.assert_allclose(distances(descriptor(p),descriptor(np.roll(p,37,axis=1))),0,atol=1e-14)

    def test_strict_monotone(self):
        red=np.random.default_rng(2).integers(0,181,(356,450)).astype(float)
        _,p=profiles(red)
        _,r=profiles(200*(red/200)**1.8+4)
        np.testing.assert_array_equal(p,r)

    def test_saturated_reference(self):
        self.assertIsNone(profiles(np.full((356,450),255))[1])

    def test_uniform_reference(self):
        self.assertIsNone(profiles(np.full((356,450),42))[1])

    def test_frequency_blind_occupancy(self):
        a=np.tile([0.,0.,1.,1.],(2,100))
        b=np.tile([0.,1.],(2,200))
        d,l=distances(descriptor(a),descriptor(b))
        self.assertEqual(d,0.)
        self.assertGreater(l,.3)

    def test_lower_band_changed(self):
        a=np.zeros((2,400))
        b=a.copy()
        b[1,:200]=1.
        d,l=distances(descriptor(a),descriptor(b))
        self.assertEqual(d,.25)
        self.assertGreater(l,0.)
