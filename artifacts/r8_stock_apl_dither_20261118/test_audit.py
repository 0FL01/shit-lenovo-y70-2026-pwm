import json
import os
from pathlib import Path
import unittest
from audit import asset, decode_packets, evidence


class Audit(unittest.TestCase):
    def test_assets_strict_even_odd(self):
        for text in ('{"a":1}', '{"a":10}'):
            b=text.encode()
            k=len(b)%2
            encoded=(b[:k]+b''.join(b[q:q+2][::-1] for q in range(k,len(b),2))).hex()
            self.assertEqual(asset(encoded),json.loads(text))
        with self.assertRaises(ValueError):
            asset('00')
    def test_packets_reject_malformed(self):
        for x in ('39','39000000000002ab','39000000000000'):
            with self.assertRaises(ValueError):
                decode_packets(bytes.fromhex(x))
    def test_archived_findings(self):
        root = os.environ.get('PWM_ARCHIVE_ROOT')
        self.assertTrue(root, 'Set PWM_ARCHIVE_ROOT to a checkout containing the original archive; this test cannot be skipped.')
        d=evidence(Path(root))
        self.assertEqual(d['cn_qdcm']['common_dither_fields'], [])
        self.assertEqual((d['dt_apl_enabled'],d['threshold'],d['max_dbv'],d['func_id']),(True,16000,16180,0))
        p=d['payloads']
        self.assertEqual(p['hbm-on'][:-1],p['panel-apl-on'])
        self.assertEqual(p['hbm-off'][:-1],p['panel-apl-off'])
        self.assertNotEqual(p['panel-apl-on'],p['panel-apl-off'])
        cfg=d['cn_qdcm']['profiles']
        self.assertEqual(len(cfg),12)
        enabled=[n for n,x in cfg.items() if x['PostBlendDither']['enable']]
        self.assertEqual(set(enabled),{'hdr-nature','hdr-vivid-300'})
        self.assertTrue(all(cfg[n]['PostBlendDither']['temporalEnable']==0 for n in enabled))
        self.assertTrue(all(p['PostBlendPaDither']['enable']==0 for p in cfg.values()))
        self.assertIsNone(d['optical_pwm_hz'])
