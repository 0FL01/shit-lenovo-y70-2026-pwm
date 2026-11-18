import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import scope_receipt_divergence as receipt
from scope_native_lags import peaks

class CaptureCheckTests(unittest.TestCase):
    def test_native_lag_comb(self):
        x=np.sin(2*np.pi*np.arange(720)/17)
        k=[a for a,b in peaks(x)]
        self.assertEqual(k,[17,34,51,68,85,102,119])

    def test_restricted_search_is_not_fundamental(self):
        a=np.tile(np.sin(2*np.pi*np.arange(450)/9.45),(356,1))
        k,r=receipt.repeat(a)
        self.assertTrue(45<=k<=68)
        self.assertGreater(r,.95)

    def test_incomplete_cannot_write(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"receipt.json"
            p.write_text(json.dumps({"phases":[{"frames":[]}]}))
            out=Path(tmp)/"analysis"
            with patch("sys.argv",["scope",str(p),str(out)]):
                with self.assertRaisesRegex(ValueError,"incomplete"):
                    receipt.main()
            self.assertFalse(out.exists())
