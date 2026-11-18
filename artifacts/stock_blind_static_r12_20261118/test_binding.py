from pathlib import Path
import json,sys,tempfile,unittest
from PIL import Image
import source_binding as b
R=Path(sys.argv.pop(1)).resolve();B=Path(sys.argv.pop(1)).resolve();P=Path(sys.argv.pop(1)).resolve()
class Checks(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();d=Path(self.t.name);self.r=d/'raw';self.r.mkdir();(self.r/'private_pages').mkdir();self.bl=d/'blind';self.bl.mkdir();self.p=P
  for p in R.iterdir():
   if p.is_file():(self.r/p.name).symlink_to(p)
  for p in (R/'private_pages').iterdir():(self.r/'private_pages'/p.name).symlink_to(p)
  for p in B.iterdir():(self.bl/p.name).symlink_to(p)
 def tearDown(self):self.t.cleanup()
 def audit(self):return b.audit(self.r,self.bl,self.p)
 def bad(self):
  with self.assertRaises(ValueError):self.audit()
 def test_good(self):self.assertTrue(self.audit()['identical_18_input_aliases'])
 def test_extra(self):(self.bl/'key_hint.txt').write_text('fake');self.bad()
 def test_commit(self):p=self.r/'private_pages'/'key.json';p.unlink();p.write_text('{}');self.bad()
 def test_prediction(self):self.p=self.r/'invalid.json';self.p.write_text('{}');self.bad()
 def test_alias(self):p=self.bl/'p01_1.png';p.unlink();p.symlink_to(B/'p01_2.png');self.bad()
 def test_page(self):p=self.r/'P00.html';p.unlink();p.symlink_to(R/'P01.html');self.bad()
 def test_source(self):p=self.r/'P00_last_source.png';a=Image.open(p).convert('RGB');p.unlink();a.putpixel((112,617),(0,1,0));a.save(p);self.bad()
if __name__=='__main__':unittest.main()
