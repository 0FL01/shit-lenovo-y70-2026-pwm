"""Offline archive mutations. Usage: python test_replay.py PRIVATE_ARCHIVE."""
import sys,tempfile,unittest
from pathlib import Path
import replay
ARCHIVE=Path(sys.argv.pop(1))
NAMES=['short_drag','short2','short3','short4']
class Test(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for n in NAMES:(self.root/(n+'_raw.txt')).write_bytes((ARCHIVE/(n+'_raw.txt')).read_bytes())
 def tearDown(self):self.tmp.cleanup()
 def change(self,old,new):
  p=self.root/'short3_raw.txt';s=p.read_text();self.assertIn(old,s);p.write_text(s.replace(old,new,1))
 def reject(self):
  with self.assertRaises((ValueError,IndexError,AttributeError,FileNotFoundError)):replay.run(self.root)
 def test_original(self):
  q=replay.run(self.root);self.assertTrue(q['four_results_advance']);self.assertEqual(len(q['samples']),4)
  self.assertIsNone(q['calibrated_preview_row_time']);self.assertIsNone(q['physical_pwm_frequency'])
  for s in q['samples']:
   self.assertNotEqual(s['result']['sensor.exposureTime'],s['last_request']['sensor.exposureTime'])
   self.assertNotIn('sensor.timestamp',s['result'])
 def test_request_as_actual(self):self.change('[156000 ]','[200000 ]');self.reject()
 def test_wrong_request(self):self.change('[200000 ]','[156000 ]');self.reject()
 def test_iso(self):self.change('[6400 ]','[6300 ]');self.reject()
 def test_skew(self):self.change('[31824000 ]','[31824001 ]');self.reject()
 def test_duration(self):self.change('[33350000 ]','[33333333 ]');self.reject()
 def test_duplicate(self):
  (self.root/'short3_raw.txt').write_bytes((self.root/'short2_raw.txt').read_bytes());self.reject()
 def test_missing(self):(self.root/'short4_raw.txt').unlink();self.reject()
 def test_camera(self):self.change('Device 2 is open.','Device 2 is closed.');self.reject()
 def test_stream(self):self.change('Dims: 1440 x 1080,','Dims: 1920 x 1080,');self.reject()
 def test_static_camera(self):
  self.change('== Camera HAL device device@1.1/internal/2 (v1.2) static information: ==','== wrong static ==');self.reject()
if __name__=='__main__':unittest.main()
