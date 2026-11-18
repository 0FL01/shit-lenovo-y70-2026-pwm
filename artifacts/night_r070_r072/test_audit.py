import unittest
from audit import PANEL, NODE, asset_join, audit, read, refresh_row


class ArchiveTests(unittest.TestCase):
    def test_complete(self):
        r = audit()
        self.assertIsNone(r['R070']['current_merged_profile'])
        self.assertIsNone(r['physical_pwm_hz'])
        self.assertEqual([x['request'] for x in r['R071']['sweep']], [120,144,120,90,120])
        self.assertEqual(r['R072']['extra_dim_snapshot_rgb_diagonal'], [1,.522,1,1])

    def join(self, fn):
        inv, r8 = read('device_inventory.json'), read('r8_stock_apl_dither_20261118/result.json')
        fn(inv,r8)
        return asset_join(inv,r8,NODE,PANEL)

    def test_hash_not_panel_label(self):
        with self.assertRaises(ValueError):
            self.join(lambda i,r: r['cn_qdcm'].update(sha256='0'*64))

    def test_temporal_not_spatial(self):
        with self.assertRaises(ValueError):
            self.join(lambda i,r: r['cn_qdcm']['profiles']['hdr-nature']['PostBlendDither'].update(temporalEnable=1))

    def test_requested_not_active(self):
        run=read('stock_base_rates_20261107/run.json'); analysis=read('stock_base_rates_20261107/analysis.json')
        with self.assertRaises(ValueError):
            refresh_row(2,dict(run['phases'][1],software_refresh_end=120.),analysis['stages'][1],analysis['native']['phases'][1])

    def test_wrong_phase(self):
        r=read('stock_base_rates_20261107/run.json'); a=read('stock_base_rates_20261107/analysis.json')
        with self.assertRaises(ValueError):
            refresh_row(3,r['phases'][2],a['stages'][0],a['native']['phases'][2])
