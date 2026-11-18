import copy
import json
import unittest
from xml.etree import ElementTree as ET
import audit as a


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.proj=json.loads((a.HERE/'projection.json').read_text())
        self.repeat=a.read('stock_dbv_association_r7_20261118/outcome.json')

    def test_full_snapshot(self):
        self.assertEqual(json.loads(json.dumps(a.run())),
                         json.loads((a.HERE/'results.json').read_text()))

    def test_changed_float_same_int(self):
        self.proj['android_calibration'][3][1]='0.14037974'
        with self.assertRaisesRegex(ValueError,'binary32'):
            a.calibration(self.proj,self.repeat)

    def test_do_not_identify_native_series_with_float_mapping(self):
        self.proj['native_direct'][2][1]='0.201'
        with self.assertRaisesRegex(ValueError,'direct controls'):
            a.calibration(self.proj,self.repeat)

    def test_changed_r7_label(self):
        s=self.repeat['phase_summaries'][2]
        s['dbv']=2632 if s['dbv']==2633 else 2633
        with self.assertRaisesRegex(ValueError,'R7'):
            a.calibration(self.proj,self.repeat)

    def test_duplicate_xml_key(self):
        xml=ET.parse(a.ART/'current_display_path/als/als_comp_config.xml')
        cfg=xml.find(".//config[@type='default']")
        cfg.append(copy.deepcopy(cfg.find('configuration')))
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            a.als(xml)

    def test_wrong_native_packet(self):
        j=a.read('exact_dbv_dispatch_20261106.json')
        j['native_brightness_packets'][1]['payload']='51 0e 10'
        with self.assertRaisesRegex(ValueError,'dispatch'):
            a.dispatch(j)

    def test_spline_not_extrapolated(self):
        with self.assertRaisesRegex(ValueError,'segment'):
            a.spline(.40987244,self.proj['spline_segment'])
