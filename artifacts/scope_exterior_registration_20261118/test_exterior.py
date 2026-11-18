import tempfile
import unittest
from pathlib import Path

import numpy as np

from exterior import BOX, score
from future import checks, reference
from validate import perturb


def specimen():
    # Fixture contains entirely invented legend glyphs, no private pixels.
    im = np.full((2392,1080,3),5,dtype=np.uint8)
    for x,y,r,b in BOX.values():
        yy,xx=np.indices((b-y,r-x))
        s=(((xx//5+yy//6)%2)>0).astype(np.uint8)*115+5
        im[y:b,x:r,:]=s[:,:,None]
    return im


class TestExterior(unittest.TestCase):
    def test_plot_is_not_geometry(self):
        a=specimen()
        b=perturb(a, "trace")
        self.assertEqual(score(a,a),score(a,b))
        self.assertTrue(checks(a,a)["pass_original_upper_headroom"])
        self.assertFalse(checks(a,b)["pass_original_upper_headroom"])

    def test_shift_blur_and_blank(self):
        a=specimen()
        self.assertTrue(score(a,a)["pass_exterior"])
        for k in ("blur","occlude","clip","weak"):
            self.assertFalse(score(a,perturb(a,k))["pass_exterior"], k)
        for v in (-4,4):
            self.assertFalse(score(a,perturb(a,"shift",v,0))["pass_exterior"])

    def test_wrong_fixed_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fake"
            path.write_bytes(b"not the frozen reference")
            with self.assertRaisesRegex(ValueError,"wrong fixed-framing"):
                reference(path)


if __name__=="__main__":
    unittest.main()
