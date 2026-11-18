import unittest
from audit import BOOK, audit, catalog, decode, render

A, B = BOOK["primary"], BOOK["reserve"]


class TestCode(unittest.TestCase):
    def test_all(self):
        out = audit()
        self.assertEqual(out["trials"], {"full": 48, "one_deletion": 576})
        self.assertEqual(out["wrong_or_unresolved"], 0)
        self.assertEqual(out["distinct_primary_profiles"], 288)
        self.assertEqual(out["reserve_overlap"], 0)

    def test_known_pattern(self):
        # +y, beginning at slot 2, missing slot 6: computed by hand.
        self.assertEqual(decode(render("y", "20201021010"), A), None)
        self.assertEqual(decode(render("y", "20210102101"), A), ("y", 1, 2, 6))

    def test_wrong_scene_or_sampling(self):
        for profile in ("0"*12, A[2:], A + A[0], "222222222221", B):
            self.assertIsNone(decode(render("x", profile), A))
        im = render("x", A)
        im[2] = im[2][:-1] + "0"
        self.assertIsNone(decode(im, A))
        self.assertIsNone(decode([A]*11, A))

    def test_symmetric_code_not_implicitly_unique(self):
        symmetric = "012" * 4
        self.assertIsNone(decode(render("y", symmetric), symmetric))

    def test_normalization_boundary(self):
        # A dropped first sample and an equivalent rotated view dropping the
        # last sample cannot identify *original* start; report retained start.
        self.assertEqual(decode(render("x", A[1:]), A), ("x", 1, 1, 0))
        with self.assertRaises(ValueError):
            catalog("011201")

if __name__ == "__main__":
    unittest.main()
