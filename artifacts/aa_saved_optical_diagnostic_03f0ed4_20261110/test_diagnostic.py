"""Offline diagnostic boundary tests. No media decode or device access."""
import copy
import json
from pathlib import Path
import unittest
import diagnostic as d

class DiagnosticTests(unittest.TestCase):
    def test_original_rejected_projection_single_field_only(self):
        original,stages,manifest=d.protocol()
        self.assertNotIn('boot_id',original['before'])
        self.assertEqual([s['label'] for s in stages],['baseline','sham_stock','return_stock'])
        self.assertEqual(manifest['projection_changes'][0]['path'],'/before/boot_id')
        self.assertFalse(manifest['acquisition_admitted'])
        self.assertFalse(manifest['qualification_eligible'])
        with self.assertRaisesRegex(ValueError,d.FAILURE):d.acquisition.validate_acquisition(original)

    def setUp(self):
        self.review=json.loads((d.ROOT/'roi_review.json').read_text())
        self.windows=json.loads((d.PRIVATE/'window_plan.json').read_text())['windows']

    def test_review_valid(self):
        rois,band=d.review_rois(self.review,self.windows)
        self.assertEqual(rois['main'],[255,245,20,330]);self.assertEqual(band,[.012,.03])

    def test_review_refuses_false_flat(self):
        self.review['roi_background_content_verified']=False
        with self.assertRaises(ValueError):d.review_rois(self.review,self.windows)

    def test_review_refuses_misleading_whole_screen_flag(self):
        self.review['flat_screen_content_verified']=True
        with self.assertRaises(ValueError):d.review_rois(self.review,self.windows)

    def test_preview_refuses_public_parent(self):
        with self.assertRaises(ValueError):d.preview_parent(d.ROOT/'new-preview',d.PRIVATE/'capture.mp4')

    def test_preview_refuses_existing_directory(self):
        with self.assertRaises(ValueError):d.preview_parent(d.PRIVATE/'native-review',d.PRIVATE/'capture.mp4')

    def test_preview_accepts_fresh_private_child(self):
        d.preview_parent(d.PRIVATE/'test-not-created-preview',d.PRIVATE/'capture.mp4')

    def test_review_refuses_overlap(self):
        self.review['rois_xywh']['right']=self.review['rois_xywh']['main']
        with self.assertRaises(ValueError):d.review_rois(self.review,self.windows)

    def test_review_refuses_wrong_video(self):
        self.review['video_sha256']='0'*64
        with self.assertRaises(ValueError):d.review_rois(self.review,self.windows)

    def test_review_refuses_short_roi(self):
        self.review['rois_xywh']['main'][3]=299
        with self.assertRaises(ValueError):d.review_rois(self.review,self.windows)

    def test_no_public_full_output(self):
        with self.assertRaises(ValueError):d.output_parent(d.ROOT/'would_leak.json')
        d.output_parent(d.PRIVATE/'new_result.json')

if __name__=='__main__':unittest.main()
