import os
import unittest
from pathlib import Path

import numpy as np

import audit as a


class Checks(unittest.TestCase):
    box = [20, 20, 45, 50]

    def test_shift_direction(self):
        rng = np.random.default_rng(730)
        ref = rng.normal(size=(100, 100))
        result = a.match(ref, np.roll(ref, (-3, 2), axis=(0, 1)), self.box)
        self.assertEqual((result['dx'], result['dy'], result['resolved']), (2, -3, True))

    def test_no_structure_or_ambiguous(self):
        z = np.zeros((100, 100))
        x = np.indices(z.shape)[1] % 3
        self.assertFalse(a.match(z, z, self.box)['resolved'])
        self.assertFalse(a.match(x, x, self.box)['resolved'])

    def test_search_boundary(self):
        z = np.random.default_rng(0).normal(size=(100, 100))
        r = a.match(z, np.roll(z, 6, axis=1), self.box)
        self.assertEqual((r['dx'], r['resolved']), (6, False))

    def test_box_alias(self):
        # 192/3=64 underlying cycles above output Nyquist (96 samples).
        x = a.raster(2, 3)
        self.assertEqual(x['visible_bins'], [32])
        self.assertFalse(x['resolved'])
        self.assertEqual(a.raster(4, 4)['flat'], 16)
        self.assertFalse(a.raster(2, 4)['resolved'])
        self.assertTrue(a.raster(4, 12)['resolved'])

    def test_signed_balanced(self):
        code = np.tile([1, -1]*4, (8, 1))
        row = np.arange(8)[:, None, None]*11
        rgb = row + code[:, :, None]*np.array([1, -2, 7])
        np.testing.assert_allclose(a.contrast(rgb, code), [2, -4, 14])
        np.testing.assert_allclose(a.contrast(rgb, -code), [-2, 4, -14])
        with self.assertRaises(ValueError):
            a.contrast(rgb, code*0)

    @unittest.skipUnless(os.environ.get('R12_PREVIEWS'), 'private PNG set not supplied')
    def test_exact_archive(self):
        self.assertEqual(a.run(Path(os.environ['R12_PREVIEWS'])), a.read(a.HERE/'outcome.json'))


if __name__ == '__main__':
    unittest.main()
