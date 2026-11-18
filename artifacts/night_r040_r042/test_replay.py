import unittest

import numpy as np

from replay import mask, profile, stats


class PixelTests(unittest.TestCase):
    def test_floor_is_not_black(self):
        frame = np.array([[[0, 20, 1], [0, 0, 0], [5, 6, 255]]], dtype=np.uint8)
        triplet = np.stack([frame, frame, frame])
        triplet[2, 0, 0, 1] += 1
        self.assertEqual(stats(triplet), dict(n_pixel_observations=9,
            channel_zero=[6, 3, 3], any_zero=6, all_zero=3, any_255=3,
            chroma_s1=3, max_rgb=255, n_coordinates=3, identical_rgb_across_three=2))

    def test_strict_threshold_no_wraparound(self):
        arr = np.array([[255, 255, 0], [18, 18, 0], [18, 19, 0], [0, 0, 255]], dtype=np.uint8)
        self.assertEqual(mask(arr).tolist(), [True, False, True, False])

    def test_component_median_after_column_sort(self):
        a = np.zeros((3, 90, 428), dtype=bool)
        a[0, :12, 27] = True
        a[1, :4, 0] = True
        a[2, :7, 6] = True
        self.assertEqual(profile(a).tolist(), [0]*427 + [7])

    def test_partial_never_full(self):
        with self.assertRaises(ValueError):
            profile(np.zeros((1, 90, 428), dtype=bool))
        with self.assertRaises(ValueError):
            stats(np.zeros((1, 190, 428, 3), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
