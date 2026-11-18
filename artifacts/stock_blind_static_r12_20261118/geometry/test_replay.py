import unittest,numpy as np,json,tempfile,argparse,sys
from pathlib import Path
import replay as r
P=None
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.ctx=r.reference(P/'short3.png');cls.g=cls.ctx.__enter__()
 @classmethod
 def tearDownClass(cls):cls.ctx.__exit__(None,None,None)
 def test_archive(self):
  actual=[]
  for n in ['short_drag','short2','short3','short4']:
   q=self.g.checks(self.g.load(P/(n+'.png')));self.assertTrue(q['pass_witness']);actual.append(dict(name=n+'.png',checks=q))
  self.assertEqual(r.render(actual),(r.D/'archive_validation.json').read_text())
 def test_four_px(self):
  for n in ['short_drag','short2','short3','short4']:
   a=self.g.load(P/(n+'.png'))
   for dx,dy in [(4,0),(-4,0),(0,4),(0,-4)]:
    with self.subTest(n=n,dx=dx,dy=dy):self.assertFalse(self.g.checks(np.roll(a,(dy,dx),(0,1)))['pass_local_translation'])
 def test_black(self):self.assertFalse(self.g.checks(np.zeros((2392,1080,3),np.uint8))['pass_witness'])
 def test_auto_clips(self):self.assertFalse(self.g.checks(self.g.load(P/'expert_wide.png'))['pass_headroom'])
 def test_shape(self):
  with self.assertRaises(ValueError):self.g.checks(np.zeros((10,10,3),np.uint8))
 def test_code_independence(self):
  a=self.g.load(P/'short3.png');before=self.g.checks(a);a[1060:1200,900:1080]=128;after=self.g.checks(a);self.assertEqual(before['local_structures'],after['local_structures'])
 def test_wrong_reference(self):
  with self.assertRaises(ValueError):
   with r.reference(P/'short2.png'):pass
 def test_tampered_template(self):
  f=self.g.D/'template0.npy';old=f.read_bytes()
  try:
   f.write_bytes(old+b'x')
   with self.assertRaises(ValueError):self.g.checks(self.g.load(P/'short3.png'))
  finally:f.write_bytes(old)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args,rest=parser.parse_known_args();P=args.archive;unittest.main(argv=[sys.argv[0]]+rest)
