import unittest

from audit import read, run


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.args = [read(n) for n in ("frames", "raster_qc", "pairs")]

    def test_archive(self):
        r = run(*self.args)
        self.assertTrue(r["raster_separated_all"])
        self.assertEqual((r["frames"], len(r["variants"])), (9, 7))
        self.assertEqual(r["nominal_Dmed"]["1_0:3_0"], 0.020208)

    def test_missing_or_duplicated_data(self):
        for i in range(3):
            for corrupt in (lambda rows: rows[:-1], lambda rows: rows + [rows[-1]]):
                with self.subTest(i=i, corrupt=corrupt), self.assertRaises(ValueError):
                    run(*(corrupt(t) if j == i else t for j, t in enumerate(self.args)))

    def test_bad_registration(self):
        self.args[1][0]["grid_dx"] = "1"
        with self.assertRaises(ValueError):
            run(*self.args)

    def test_equal_edge_is_not_separated(self):
        for r in self.args[2]:
            if (r["ref_q"], r["dx"], r["dy"]) == ("0.97", "0", "0"):
                for key in ("Dmin", "Dmed", "Dmax"):
                    r[key] = "0.2"
        result = run(*self.args)
        self.assertFalse(result["raster_separated_all"])
        self.assertEqual(min(v["margin"] for v in result["variants"]), 0)


if __name__ == "__main__":
    unittest.main()
