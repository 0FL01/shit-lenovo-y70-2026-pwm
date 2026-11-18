import tempfile
import unittest
from pathlib import Path
import numpy as np
from audit import audit, counts, veto


class Checks(unittest.TestCase):
    def test_overlapping_and_distinct_rails(self):
        a = np.array([[[0, 255, 7], [12, 0, 100], [255, 7, 15], [6, 3, 90]]],
                     dtype=np.uint8)
        self.assertEqual(counts(a), [2, 2, 3])

    def test_nonrail_is_not_linear_proof(self):
        self.assertEqual(counts(np.full((3, 7, 3), 4, dtype=np.uint8)), [0, 0, 0])

    def test_exact_threshold_is_rejected(self):
        self.assertFalse(veto(703, 70400))
        self.assertTrue(veto(704, 70400))
        self.assertTrue(veto(705, 70400))

    def test_no_incomplete_phases(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "spatial-1A-1.png").touch()
            with self.assertRaisesRegex(ValueError, "inventory"):
                audit(Path(t), "spatial", {})

    def test_non_rgb_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "RGB8"):
            counts(np.zeros((2, 3), dtype=np.uint8))
