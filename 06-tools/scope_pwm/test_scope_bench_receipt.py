"""Contract tests for trusted bench receipts, including all three public CLIs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scope_bench_receipt import FIELDS, read_receipt
import scope_receipt_divergence, scope_raster_qc, scope_native_lags

def fixture():
    def stamp(t): return f"2026-11-18T11:00:{t:02d}+00:00"
    def state(t): return {"utc":stamp(t),**{k:"x" for k in FIELDS}}
    phases=[]
    for n in range(3):
        start=n*10+1
        phases.append({"phase":str(n),"start":state(start),"end":state(start+4),
                       "frames":[[f"frame_{n}_{i}",stamp(start+i)] for i in (1,2,3)]})
    return {"initial":state(0),"phases":phases,"restored":state(20)}

class GuardTests(unittest.TestCase):
    def check(self,j,error=None):
        with TemporaryDirectory() as d:
            p=Path(d)/"r.json"
            p.write_text(json.dumps(j))
            if error:
                with self.assertRaisesRegex(ValueError,error):
                    read_receipt(p)
            else:
                self.assertEqual(j,read_receipt(p))

    def test_post_restore_frames(self):
        self.check(fixture())

    def test_restore_must_cover_experimental_phases(self):
        j=fixture()
        for seconds in (7, 13, 23):
            with self.subTest(seconds=seconds):
                j["restored"]["utc"]=f"2026-11-18T11:00:{seconds:02d}+00:00"
                self.check(j,"restoration")
        j=fixture()
        j["phases"][-1]["start"]["dc"]=j["phases"][-1]["end"]["dc"]="other"
        self.check(j,"restoration")
        j["restored"]["utc"]="2026-11-18T11:00:27+00:00"
        self.check(j)

    def test_missing_state_all_endpoints(self):
        for key in ("initial","restored","start","end"):
            with self.subTest(key=key):
                j=fixture()
                (j if key in ("initial","restored") else j["phases"][0]).pop(key)
                self.check(j,"incomplete")

    def test_empty_or_duplicate_phase(self):
        for name in ("","1"):
            j=fixture()
            j["phases"][0]["phase"]=name
            self.check(j,"phase")
        j=fixture()
        j["phases"]=[]
        self.check(j,"incomplete")

    def test_duplicate_stem_fails_all_clis_no_output(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"r.json"
            j=fixture()
            j["phases"][2]["frames"][2][0]=j["phases"][0]["frames"][0][0]
            p.write_text(json.dumps(j))
            for mod in (scope_receipt_divergence,scope_raster_qc,scope_native_lags):
                out=Path(d)/mod.__name__
                with patch("sys.argv",["scope",str(p),str(out)]):
                    with self.assertRaisesRegex(ValueError,"duplicate frame"):
                        mod.main()
                self.assertFalse(out.exists())

    def test_changed_checked_state(self):
        j=fixture()
        j["restored"]["dc"]="1"
        self.check(j,"initial/restored")
        j=fixture()
        j["phases"][0]["end"]["brightness"]="1"
        self.check(j,"endpoints")

    def test_frame_time_traversal_and_count(self):
        j=fixture()
        j["phases"][0]["frames"][2][1]=j["initial"]["utc"]
        self.check(j,"out of order")
        j=fixture()
        j["phases"][0]["frames"][2][0]="../other"
        self.check(j,"basename")
        j=fixture()
        j["phases"][0]["frames"].pop()
        self.check(j,"incomplete")
