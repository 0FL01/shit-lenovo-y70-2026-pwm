import unittest
from replay import ARCHIVE, count_panel, count_r7, read_rows, replay


class ArchiveCounts(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows(ARCHIVE/"night_r031_r033/legend_reads.csv")

    def test_observed(self):
        data = replay()
        r = data["R7"]
        self.assertEqual((r["planned"], r["captured"]), (51,43))
        self.assertEqual(r["original_qc"], {"accepted":42,"rejected":1,"missing":8})
        self.assertEqual(r["coupling_label"], {"AC":43})
        self.assertEqual(r["dc_labels_requiring_review_not_qualified_pairs"], [])
        for k in ("panelDC_3600", "panelDC_3601"):
            self.assertEqual(data[k], {"frame_rows":9,"raster_qc":{"ok":9},
                             "per_phase":{"1_0":3,"2_1":3,"3_0":3}})

    def test_preserve_new_label_for_review(self):
        self.rows[1]["coupling"] = "DC"
        self.assertEqual(count_r7(self.rows)["dc_labels_requiring_review_not_qualified_pairs"],
                         [self.rows[1]["slot"]])

    def test_unread_is_not_dc_or_ac(self):
        self.rows[1]["coupling"] = ""
        self.assertEqual(count_r7(self.rows)["coupling_label"], {"AC":42, "unread":1})

    def test_refuse_invented_slot_data(self):
        self.rows[-1]["coupling"] = "AC"
        with self.assertRaises(ValueError):
            count_r7(self.rows)

    def test_refuse_duplicate_slot(self):
        self.rows[-1] = self.rows[-2]
        with self.assertRaises(ValueError):
            count_r7(self.rows)

    def test_refuse_duplicate_capture(self):
        r = {"capture":"same","status":"ok","phase":"1_0"}
        with self.assertRaises(ValueError):
            count_panel([r,r])


if __name__ == "__main__":
    unittest.main()
