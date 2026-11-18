import argparse,unittest,tempfile,json,sys
from pathlib import Path
import capture_replay as c
import replay
REF=None;CAP=None
class Tests(unittest.TestCase):
 def test_exact_actual(self):
  z=c.run(REF,CAP);self.assertEqual(replay.render(z),(replay.D/'actual_capture.json').read_text())
  self.assertEqual([r['name'] for r in z if not r['checks']['pass_witness']],['p02_3.png','p04_1.png','p04_3.png'])
  self.assertEqual(sum(r['checks']['pass_witness'] for r in z),15)
  self.assertTrue(all(r['checks']['pass_headroom'] for r in z))
  self.assertEqual({r['name']:r['checks']['any_zero'] for r in z if r['checks']['any_zero']},{'p01_3.png':3,'p06_1.png':18})
 def make_links(self,root):
  for n in c.NAMES:(root/n).symlink_to(CAP/n)
 def test_missing(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.make_links(p);(p/c.NAMES[-1]).unlink()
   with self.assertRaises(ValueError):c.paths(p)
 def test_extra(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.make_links(p);(p/'extra.png').symlink_to(CAP/c.NAMES[0])
   with self.assertRaises(ValueError):c.paths(p)
 def test_duplicate(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.make_links(p);(p/c.NAMES[-1]).unlink();(p/c.NAMES[-1]).symlink_to(CAP/c.NAMES[0])
   with self.assertRaises(ValueError):c.paths(p)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('capture',type=Path);a,rest=p.parse_known_args();REF=a.reference.resolve();CAP=a.capture.resolve();unittest.main(argv=[sys.argv[0]]+rest)
