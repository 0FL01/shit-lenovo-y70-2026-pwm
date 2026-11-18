import unittest
import audit


class Evidence(unittest.TestCase):
    def test_chronology(self):
        rows = audit.audit()["dc_phase_rows"]
        self.assertEqual([r[-1] for r in rows], [["on","off"],["on"],["off"],[],["on"],["off"]])
        self.assertEqual([r[1:4] for r in rows], [[s,s,b] for b in (5197,2839) for s in (0,1,0)])

    def test_reject_state_disagreement(self):
        t = audit.obj("stock_dc_trial_20261106.json")
        t["phases"][1]["observed"]["panel_dc"] = "0"
        with self.assertRaisesRegex(ValueError,"mismatch"):
            audit.dc(t,audit.obj("stock_dc_trace_analysis_20261106.json"))

    def test_reject_wrong_marker(self):
        t = audit.obj("stock_dc_trace_analysis_20261106.json")
        t["exact_dc_set_matches"][0]["phase"] = t["markers"][1]["phase"]
        with self.assertRaisesRegex(ValueError,"misassigned"):
            audit.dc(audit.obj("stock_dc_trial_20261106.json"),t)

    def test_reject_dbv_confound(self):
        x = audit.obj("STOCK_EXTRA_DIM_20261118_data.json")
        x["target_snapshots"]["on1_pre"]["fields"]["panel_brightness"] += 1
        with self.assertRaisesRegex(ValueError,"isolated"):
            audit.extra(x,audit.obj("stock_extra_dim_locked_20261118/observations.json"))

    def test_separate_cap_from_readback(self):
        a = audit.apl()
        self.assertEqual((a["threshold"], a["first_on_candidate"], a["max_class"]),(16000,16001,16180))
        self.assertLess(a["pre_and_post_native"],a["estimated_native_at_cap"])
        self.assertLess(a["estimated_native_at_cap"],a["first_on_candidate"])


if __name__ == "__main__":
    unittest.main()
