"""Offline regression suite; pass the private evidence directory as argv[1]."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import replay

ROOT = Path(sys.argv.pop(1))
REAL_LOAD = replay.load


class ReplayTests(unittest.TestCase):
    def reject(self, edits):
        def edited(root, name):
            value = copy.deepcopy(REAL_LOAD(root, name))
            if name in edits:
                value = edits[name](value)
            return value
        with patch.object(replay, 'load', side_effect=edited):
            with self.assertRaises(ValueError):
                replay.replay(ROOT)

    def test_original(self):
        replay.replay(ROOT)

    def test_duplicate_oc_restore(self):
        self.reject({'oc_restored_all_b_read0':
                     lambda _: REAL_LOAD(ROOT, 'oc_restored_all_read0')})

    def test_wrong_oc_camera(self):
        for name in ('oc_first', 'oc_restored_all_read0', 'oc_restored_all_b_read0'):
            with self.subTest(name=name):
                self.reject({name: lambda m: dict(m, camera='other')})

    def test_nonadvancing_oc_restore(self):
        first = REAL_LOAD(ROOT, 'oc_restored_all_read0')
        for key in ('request.frameCount', 'sensor.timestamp'):
            for offset in (0, -1):
                def change(m):
                    m['res'][key] = str(int(first['res'][key]) + offset)
                    return m
                with self.subTest(key=key, offset=offset):
                    self.reject({'oc_restored_all_b_read0': change})

    def test_nonadvancing_stock_restore(self):
        first = REAL_LOAD(ROOT, 'stock_final0')
        for key in ('request.frameCount', 'sensor.timestamp'):
            for offset in (0, -1):
                def change(m):
                    m[key] = str(int(first[key]) + offset)
                    return m
                with self.subTest(key=key, offset=offset):
                    self.reject({'stock_final_b0': change})

    def test_one_clipped_face_pixel(self):
        real_open = replay.Image.open
        def clipped(path):
            with real_open(path) as original:
                altered = original.copy()
            altered.putpixel((200, 1100), (255, 255, 255))
            return altered
        with patch.object(replay.Image, 'open', side_effect=clipped):
            with self.assertRaisesRegex(ValueError, 'edge/highlight gate'):
                replay.replay(ROOT)

    def test_wrong_focus_and_stock_zoom(self):
        def focus(m):
            m['res']['lens.focusDistance'] = '2.00000000'
            return m
        self.reject({'qualified2_read0': focus})
        self.reject({'stock_final_b0': lambda m: dict(m, **{'control.zoomRatio': '1.00000000'})})


if __name__ == '__main__':
    unittest.main()
