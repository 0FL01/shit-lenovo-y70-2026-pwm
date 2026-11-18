import json, shutil, sys, tempfile, unittest
from pathlib import Path
import release_replay as r
from PIL import Image
D=Path(sys.argv.pop(1))
class Test(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.f=Path(self.t.name)
  for n in ('log.jsonl','target_pre.png','fresh_target.png','r11_target_after.png','staticA_target.png','held_static_target.png','release_target_extra.txt','expert_wide_metadata.json','wide_auto_return_metadata.json','expert_first_metadata.json','expert_main_return_metadata.json','camera_pre.json','restoredA.json','restoredB.json'):shutil.copyfile(D/n,self.f/n)
 def tearDown(self):self.t.cleanup()
 def bad(self):
  with self.assertRaises((ValueError,KeyError)):r.audit(self.f)
 def test_good(self):self.assertEqual(r.audit(self.f)['stock_controls_equal'],15)
 def test_repeat(self):shutil.copyfile(self.f/'restoredA.json',self.f/'restoredB.json');self.bad()
 def test_wrong_expert(self):
  f=self.f/'wide_auto_return_metadata.json';z=json.loads(f.read_text());z['control.aeMode']='OFF';f.write_text(json.dumps(z));self.bad()
 def test_drift(self):
  f=self.f/'held_static_target.png';im=Image.open(f).convert('RGB');im.putpixel((350,400),(0,1,2));im.save(f);self.bad()
 def test_native(self):
  f=self.f/'log.jsonl';f.write_text(f.read_text().replace('panel_brightness=6879','panel_brightness=828',1));self.bad()
if __name__=='__main__':unittest.main()
