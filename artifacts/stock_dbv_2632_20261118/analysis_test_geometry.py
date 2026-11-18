"""Self-contained, synthetic structural gate checks; no camera, ADB or private files."""
import unittest

import numpy as np
from PIL import Image, ImageFilter

from analysis_geometry import ANCHORS, reference, score


def fixture():
    im=np.full((2392,1080,3),18,np.uint8)
    for _,(l,t,r,b),axis,n in ANCHORS:
        for dx,val in zip(range(-3,4), [1,10,42,60,43,10,1]):
            if axis=="x":
                im[t:b,n+dx,2]=18+val
            else:
                im[n+dx,l:r,2]=18+val
    return im


class Geometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.img=fixture()
        cls.ref=reference([cls.img]*3)  # tests geometry only; acquisition checks are separate

    def test_fixture_and_intentionally_changed_waveform(self):
        alt=self.img.copy()
        # Bright yellow crests in the old green-border ROI including a false edge at x534.
        alt[1009:1052,535:540]=[192,178,7]
        alt[1090:1255,118:535:9]=[200,193,3]
        self.assertTrue(score(alt,self.ref)["pass_geometry_highlights"])
        self.assertEqual(score(alt)["anchors"],score(self.img)["anchors"])

    def test_translations(self):
        for axis in (0,1):
            for shift in (-5,5):
                with self.subTest(axis=axis,shift=shift):
                    self.assertFalse(score(np.roll(self.img,shift,axis=axis),self.ref)["pass_geometry_highlights"])

    def test_local_deformation_and_wrong_color(self):
        alt=self.img.copy()
        alt[1258:1272]=np.roll(alt[1258:1272],6,axis=1)
        self.assertFalse(score(alt,self.ref)["pass_geometry_highlights"])
        self.assertFalse(score(self.img[:,:,[2,1,0]],self.ref)["pass_geometry_highlights"])

    def test_blur_occlusion_and_dim_reference(self):
        blurred=np.asarray(Image.fromarray(self.img).filter(ImageFilter.GaussianBlur(3)))
        self.assertFalse(score(blurred,self.ref)["pass_geometry_highlights"])
        occluded=self.img.copy()
        occluded[974:1005,542:569]=[160,125,8]
        self.assertFalse(score(occluded,self.ref)["pass_geometry_highlights"])
        with self.assertRaises(ValueError):
            reference([self.img,self.img,occluded])
        muted=18+((self.img-18)*.5).astype(np.uint8)
        self.assertFalse(score(muted,self.ref)["pass_geometry_highlights"])

    def test_clipping_and_floor_reporting(self):
        for row,col,ch,v in [(1050,105,0,255),(1200,115,1,250)]:
            alt=self.img.copy();alt[row,col,ch]=v
            self.assertIn("highlights",score(alt,self.ref)["failures"])
        alt=self.img.copy();alt[1190:1200,130:140,2]=0
        self.assertEqual(score(alt)["trace_zero_rgb"],[0,0,100])

    def test_input_checks(self):
        with self.assertRaises(ValueError): score(self.img[:100])
        with self.assertRaises(ValueError): score(self.img.astype(float))
        with self.assertRaises(ValueError): reference([self.img]*2)


if __name__=="__main__":
    unittest.main()
