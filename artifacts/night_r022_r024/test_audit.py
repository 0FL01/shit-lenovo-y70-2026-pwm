import json
import os
from pathlib import Path
import unittest

from audit import HERE, ART, classify, partition, run, streams, ui


class AuditTests(unittest.TestCase):
    def test_aspect_is_not_scenario(self):
        for size, target, wanted in [((3264,2448),(1440,1080),'uniform_scale_15/34'),
                                     ((3264,2448),(3264,2448),'equal_size'),
                                     ((3264,1836),(1920,1088),'aspect_change_required'),
                                     ((3264,1836),(1440,1080),'aspect_change_required')]:
            self.assertEqual(classify(size, target), wanted)

    def test_coded_denominator_and_missing_slot(self):
        rows = json.loads((ART/'night_r016_r018_20261118/outcome.json').read_text())['R018']
        self.assertEqual(partition(rows), {'both_pass':6, 'signal_only_fails':6, 'geometry_only_fails':3, 'both_fail':0})
        rows.pop('p05_1.png')
        with self.assertRaises(ValueError):
            partition(rows)

    def test_legacy_rotation_is_not_a_display_report(self):
        with self.assertRaises(ValueError):
            ui('ACTIVITY com.nothing.camera/.A\n rotation: 0\n')
        with self.assertRaises(ValueError):
            streams('Stream[0]: Output\n Dims: 1440 x 1080, format 0x11,')

    @unittest.skipUnless(os.getenv('R11_ARCHIVE') and os.getenv('GC08_SOURCE'), 'requires archived R11 and pinned C source')
    def test_exact_replay_and_limits(self):
        out = run(Path(os.environ['R11_ARCHIVE']), Path(os.environ['GC08_SOURCE']))
        self.assertEqual(out, json.loads((HERE/'outcome.json').read_text()))
        self.assertIsNone(out['R024']['selected_sensor_scenario'])
        self.assertIsNone(out['R023']['readout_axis_sign'])
        for s in out['R023']['samples'].values():
            self.assertEqual([x['index'] for x in s['streams'] if x['frames_produced'] > 0], [0])
            self.assertEqual(s['ui']['render_frame_parent_rect'], [0,261,1080,1701])
            self.assertEqual(s['screenshot_size'], [1080,2392])
            self.assertEqual(s['active_rect'], s['result_crop'])


if __name__ == '__main__':
    unittest.main()
