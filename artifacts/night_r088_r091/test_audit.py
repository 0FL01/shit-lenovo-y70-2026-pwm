import json
import unittest
from fractions import Fraction as Q
from pathlib import Path
from audit import inventory
from period_bounds import period, relation


class Offline(unittest.TestCase):
    def test_source_replay(self):
        self.assertEqual(inventory(), json.loads(Path(__file__).with_name('inventory.json').read_text()))

    def test_scale_and_endpoint_uncertainty(self):
        p = period(('1', '1.1'), ('9', '9.1'), ('.0049', '.0051'), 4)
        self.assertEqual(p, (Q('7.9')*Q('.0049')/4, Q('8.1')*Q('.0051')/4))
        # Omitting calibration error would spuriously separate these synthetic periods.
        self.assertEqual(relation(p, (Q('.0103'), Q('.0103'))), 'compatible_not_equal')

    def test_disjoint_and_touch(self):
        self.assertEqual(relation((2, 3), (4, 5)), 'shorter')
        self.assertEqual(relation((4, 5), (2, 3)), 'longer')
        self.assertEqual(relation((2, 3), (3, 5)), 'compatible_not_equal')

    def test_invalid_bounds(self):
        for args in [((1, 2), (2, 3), (1, 1), 2), ((1, 1), (2, 2), (0, 1), 2),
                     ((0, 1), (2, 3), (1, 1), True), ((1, 0), (2, 3), (1, 1), 2)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                period(*args)


if __name__ == '__main__':
    unittest.main()
