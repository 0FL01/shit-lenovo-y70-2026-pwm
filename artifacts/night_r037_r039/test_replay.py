import json
import os
import unittest
import tempfile
from pathlib import Path

import numpy as np

import replay as m

SAVED=json.loads(Path(__file__).with_name('outcome.json').read_text())


class TestCorpus(unittest.TestCase):
    def test_all_doublets_and_refusals(self):
        results = [m.doublet(s,h) for s in (24,18) for h in (40,38,32,20)]
        self.assertEqual(results,SAVED['R037'])
        self.assertEqual((results[0]['minimal_period_px'],results[0]['edge_px']),(24,24))
        self.assertEqual(results[1]['minimal_period_px'],48)
        self.assertLess(results[1]['edge_px'],25)
        self.assertFalse(results[1]['cycle_variation_flag'])
        self.assertTrue(results[2]['cycle_variation_flag'])
        self.assertEqual([x['edge_px'] for x in results[4:]],[None,None,None,48])
        self.assertTrue(all(x.get('detector_fundamental') is None for x in results))

    def test_exterior_same_mean_and_texture(self):
        x=np.arange(48,dtype=np.int16).reshape(4,4,3)
        d=m.div.descriptor(np.zeros((2,400)))
        def metric(y):return m.metrics((d,x),(d,y))
        self.assertEqual(metric(x),(0,0,0))
        self.assertEqual(metric(x+20),(0,20,20))
        self.assertGreater(metric(x[::-1])[1],0)
        self.assertEqual(metric(x[::-1])[2],0)

    def test_wrong_spatial_bytes_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)
            (src/'spatial-1A-1.png').write_bytes(b'wrong original')
            with self.assertRaisesRegex(ValueError, 'wrong spatial original: spatial-1A-1'):
                m.spatial(src)

    @unittest.skipUnless(os.getenv('NIGHT_CAL_PNG'), 'private calibration originals absent')
    def test_calibration_reference_and_refusals(self):
        out=m.scope_states(Path(os.environ['NIGHT_CAL_PNG']))
        self.assertEqual(out,SAVED['R038'])
        self.assertEqual([x['phase'] for x in out if x['lower'] is None],['after','after'])
        self.assertGreater(min(x['lower'] for x in out if x['phase']=='off'),
                           max(x['lower'] for x in out if x['phase'] in ('before','restored')))

    @unittest.skipUnless(os.getenv('NIGHT_SPATIAL_PNG'),'private final spatial v2 absent')
    def test_spatial_archive(self):
        out=json.loads(json.dumps(m.spatial(Path(os.environ['NIGHT_SPATIAL_PNG']))))
        self.assertEqual(out,SAVED['R039'])
        self.assertEqual(out['n_pairs'],{'same':51,'different':54})
        self.assertTrue(all(v['gap']>0 for v in out['scores'].values()))


if __name__=='__main__':
    unittest.main()
