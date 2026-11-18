from copy import deepcopy
from pathlib import Path
import json
import os
import unittest

from audit import score_controls, error_map, match, run


class Tests(unittest.TestCase):
    def test_imbalance_oracle(self):
        a = [1,-1]*32
        b = [-x for x in a]
        rows = [("p01_1",a,a),("p02_1",b,b)]
        self.assertEqual(score_controls(rows)["fixed_upper_bound"],64)
        self.assertEqual(score_controls(rows+[("p03_1",a,a)])["fixed_upper_bound"],128)

    def test_repeat_vs_phase(self):
        a = [1]*64
        p = a[:]; p[0]=-1; p[9]=-1
        q = a[:]; q[9]=-1
        m=error_map([("p01_1",a,p),("p01_2",a,p),("p02_1",a,q)])
        self.assertEqual(m["areas"]["edge"],{"errors":2,"opportunities":84})
        self.assertEqual(m["areas"]["center"],{"errors":3,"opportunities":108})
        self.assertEqual([(x["repeat"],x["across_phases"]) for x in m["cells"]],
                         [(True,False),(True,True)])

    def test_bracket(self):
        raw = dict(result={"sensor.exposureTime":"10","sensor.sensitivity":"2"},
                   request={"sensor.exposureTime":"12"}, frame_offset=0,timestamp_offset_ns=0)
        op = dict(ordinal="P00_0",image=dict(sha256="a"),pre=raw,
                  post=dict(raw,frame_offset=3,timestamp_offset_ns=24),
                  displayed_sensor_frame_identity="unknown")
        def f(rows):
            return match("p01_1.png","a",{"p01_1.png":"a"},rows)
        self.assertEqual(f([op])["sensor_frame"],"unknown")
        self.assertEqual(f([])["status"],"no unique matching image")
        self.assertEqual(f([op,op])["status"],"no unique matching image")
        self.assertEqual(f([dict(op,ordinal="P00_1")])["status"],"ordinal mismatch")
        self.assertEqual(f([dict(op,post={})])["status"],"incomplete bracket")
        x=deepcopy(op); x["post"]["result"]=dict(x["post"]["result"])
        x["post"]["result"]["sensor.sensitivity"]="5"
        self.assertEqual(f([x])["status"],"inconsistent bracket")
        self.assertEqual(f([dict(op,post=raw)])["status"],"inconsistent bracket")

    @unittest.skipUnless(os.getenv("R12B_ARCHIVE"),"set R12B_ARCHIVE for aggregate replay")
    def test_archive(self):
        d=Path(__file__).parent
        a=run(Path(os.environ["R12B_ARCHIVE"]),d/"inputs.sha256")
        self.assertEqual(a,json.loads((d/"outcome.json").read_text()))
        self.assertEqual((len(a["R018"]), sum(x["sensor_frame"]=="unknown" for x in a["R018"].values())),(18,18))

if __name__=="__main__":
    unittest.main()
