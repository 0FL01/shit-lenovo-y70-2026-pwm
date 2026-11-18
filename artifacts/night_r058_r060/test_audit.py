import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from audit import paired_slots, read, summary

class CoverageTests(unittest.TestCase):
    def test_changed_source_rejected(self):
        with TemporaryDirectory() as tmp:
            rel = "night_r031_r033/outcome.json"
            path = Path(tmp) / rel
            path.parent.mkdir()
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "differs from source pin"):
                read(rel, Path(tmp))

    def test_historical_coverage(self):
        s = summary()
        self.assertEqual(s["r11_paired_direct_background_slots"], 5)
        self.assertEqual(s["r51_processed_C_R_slots"], {"WBW": 9, "spatial": 15})
        self.assertEqual(s["r54_new_device_frames"], 0)
        self.assertIsNone(s["r54_physical_time_unit"])
        self.assertEqual(sum(s["r55_synthetic_traces_by_outcome"].values()), 1920)
        self.assertEqual(s["r55_synthetic_traces_by_outcome"]["accepted"], 799)

    def test_unequal_slot_counts_rejected(self):
        with self.assertRaises(ValueError):
            paired_slots([{"regions": {k: {"slot_counts_floor_ceiling_union": [0]*n}
                                      for k,n in [("C", 3), ("R", 2)]}}])

    def test_empty_pair_not_a_slot(self):
        with self.assertRaises(ValueError):
            paired_slots([{"regions": {k: {"slot_counts_floor_ceiling_union": []}
                                      for k in ["C", "R"]}}])
