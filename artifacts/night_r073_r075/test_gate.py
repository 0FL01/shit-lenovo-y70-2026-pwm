import unittest
from gate import classify, sham_ok


def rows(a=400,b=400,c=400):
    return [[a]*3, [b]*3, [c]*3]


class FrozenGate(unittest.TestCase):
    def test_sham_boundary(self):
        self.assertTrue(sham_ok(rows(400,430,401)))
        self.assertFalse(sham_ok(rows(400,431,401)))
        self.assertEqual(classify(rows(400,431,401), []), "STOP_SHAM")

    def test_both_directions_strict_margin(self):
        for y in (339,461):
            self.assertEqual(classify(rows(), rows(b=y)), "CANDIDATE_RASTER_ONLY")
        for y in (340,400,460):
            self.assertEqual(classify(rows(), rows(b=y)), "NOT_SEPARATED")

    def test_no_median_only_rescue(self):
        a=rows(b=500)
        a[1][2]=450
        self.assertEqual(classify(rows(), a), "INCONCLUSIVE_DRIFT")
        a=rows(b=470)
        a[0][0]=415
        self.assertEqual(classify(rows(), a), "NOT_SEPARATED")

    def test_both_off_and_sham_checked(self):
        self.assertEqual(classify(rows(), rows(b=700,c=431)), "INCONCLUSIVE_DRIFT")
        self.assertEqual(classify(rows(390,400,400), rows(421,600,421)), "INCONCLUSIVE_DRIFT")

    def test_malformed_and_missing_not_substituted(self):
        for bad in ([], [[0]*3]*2, [[0]*2]*3, rows(b=0.5), rows(c=True), rows(a=1001), rows(b=-1)):
            with self.assertRaises(ValueError):
                sham_ok(bad)
            with self.assertRaises(ValueError):
                classify(rows(), bad)
