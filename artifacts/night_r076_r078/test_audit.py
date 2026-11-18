import csv
import unittest
from audit import DC, ROOT, load, result


class TestReplay(unittest.TestCase):
    def setUp(self):
        with (ROOT/'scope_dc_divergence_20261118'/'pairs.csv').open() as f:
            self.rows = list(csv.DictReader(f))

    def test_matched_archive_controls(self):
        out = result()
        self.assertEqual([out[k]['separated_variants_of_7']
                          for k in ('dc_3600','dc_3601','boundary')], [7,0,7])
        self.assertEqual(out['boundary']['primary_control_Dmed']['base -> restored'], 0.018681)

    def test_missing_duplicate(self):
        for rows in (self.rows[:-1], self.rows + self.rows[:1]):
            with self.subTest(size=len(rows)), self.assertRaises(ValueError):
                load(rows, DC)

    def test_bad_counts_or_nonfinite(self):
        for changes in ({'n':'9'}, {'Dmed':'nan'}, {'a':'unknown'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                load([dict(self.rows[0], **changes)] + self.rows[1:], DC)
