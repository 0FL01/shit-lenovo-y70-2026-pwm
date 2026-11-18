import hashlib
import io
import json
import os
from pathlib import Path
import unittest

import numpy as np
from PIL import Image, ImageChops
from audit import firsts, run


class Checks(unittest.TestCase):
    def test_container_encoding_is_not_a_pixel_change(self):
        rgb = np.arange(48,dtype='uint8').reshape(4,4,3)
        im = Image.fromarray(rgb)
        packed, pixels = [], []
        for level in (0,9):
            f = io.BytesIO()
            im.save(f,format='PNG',compress_level=level)
            packed.append(f.getvalue())
            f.seek(0)
            with Image.open(f) as p:
                pixels.append(hashlib.sha256(p.convert('RGB').tobytes()).hexdigest())
        self.assertEqual(firsts(packed), [0,1])
        self.assertEqual(firsts(pixels), [0])

    def test_control_direction_and_no_wrapping_in_bounds(self):
        a = np.arange(1080,dtype='uint16')[None,:]
        # Direct preview y unchanged; 900…1079 must read 100…279.
        im = Image.fromarray(np.tile((a%251).astype('uint8'), (3,1)))
        b = np.asarray(ImageChops.offset(im,800,0))
        np.testing.assert_array_equal(b[:,900:1080],np.asarray(im)[:,100:280])

    @unittest.skipUnless('R12_ROOT' in os.environ and 'R12_PREVIEWS' in os.environ,'private inputs required')
    def test_real_archive(self):
        d = run(Path(os.environ['R12_ROOT']),Path(os.environ['R12_PREVIEWS']))
        self.assertEqual(d, json.loads(Path(__file__).with_name('result.json').read_bytes()))
        self.assertEqual(d['R019']['retained_after_rgb_dedup'],18)
        self.assertIs(d['R019']['after_dedup'],False)
        self.assertEqual(d['R020']['series_pass'],0)
        self.assertEqual(d['R021']['false_call_frames'],0)
        self.assertEqual(d['R021']['endpoint_free_frames'],18)


if __name__ == '__main__':
    unittest.main()
