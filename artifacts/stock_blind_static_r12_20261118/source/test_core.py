"""Offline regression tests on caller-supplied historical raw and fresh log."""
import sys,json,tempfile,unittest
from pathlib import Path
import operator_core as c
import state_qa as s
RAW=Path(sys.argv.pop(1)).read_text();LOG=Path(sys.argv.pop(1))
class Tests(unittest.TestCase):
 def check_raw(self,t):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.txt';p.write_text(t);return c.raw(p)
 def test_raw(self):self.assertEqual(self.check_raw(RAW)['result']['sensor.exposureTime'],'156000')
 def test_actual(self):
  with self.assertRaises(c.Reject):self.check_raw(RAW.replace('[156000 ]','[200000 ]',1))
 def test_request(self):
  with self.assertRaises(c.Reject):self.check_raw(RAW.replace('[200000 ]','[156000 ]',1))
 def test_iso(self):
  with self.assertRaises(c.Reject):self.check_raw(RAW.replace('[6400 ]','[6300 ]',1))
 def test_camera(self):
  with self.assertRaises(c.Reject):self.check_raw(RAW.replace('Device 2 is open.','Device 2 is closed.',1))
 def test_advancement(self):
  r=self.check_raw(RAW)
  with self.assertRaises(c.Reject):c.advancing([r,r])
 def test_empty(self):
  with self.assertRaises(c.Reject):c.advancing([])
 def test_target(self):
  e=s.events(LOG);self.assertEqual(s.target(e['before_r12'][1])['native'],'6879')
 def test_missing_key(self):
  e=s.events(LOG);t=e['before_r12'][1].replace('reduce_bright_colors_level=null','removed')
  with self.assertRaises(c.Reject):s.target(t)
 def test_dc(self):
  e=s.events(LOG);t=e['before_r12'][1].replace('panelDC=0','panelDC=1')
  with self.assertRaises(c.Reject):s.target(t)
if __name__=='__main__':unittest.main()
