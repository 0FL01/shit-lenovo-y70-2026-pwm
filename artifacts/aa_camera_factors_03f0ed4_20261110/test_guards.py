import hashlib, tempfile, unittest
from pathlib import Path
from guards import private_destination, pinned_bytes
class Guards(unittest.TestCase):
 def test_bad_roots(self):
  for p in ('/tmp/legion-y70-camera-factors-03f0ed4-test','relative','/home/opencode/.cache/other','/home/opencode/.cache/nested/legion-y70-camera-factors-03f0ed4-x'):
   with self.assertRaises(ValueError):private_destination(p)
 def test_good_new(self):
  p=Path('/home/opencode/.cache/legion-y70-camera-factors-03f0ed4-never-created-unit')
  self.assertEqual(private_destination(p),p)
 def test_pin(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_bytes(b'abc');h=hashlib.sha256(b'abc').hexdigest()
   self.assertEqual(pinned_bytes(p,h,3),b'abc')
   with self.assertRaises(ValueError):pinned_bytes(p,h,2)
   with self.assertRaises(ValueError):pinned_bytes(p,'0'*64,3)
   q=Path(d)/'link';q.symlink_to(p)
   with self.assertRaises(ValueError):pinned_bytes(q,h,3)
if __name__=='__main__':unittest.main()
