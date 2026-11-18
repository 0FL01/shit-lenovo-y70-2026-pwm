"""R12a incomplete/return regression: caller provides private stopped archive."""
import sys,shutil,tempfile,json,unittest
from pathlib import Path
import replay
ROOT=Path(sys.argv.pop(1))
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for n in ['log.jsonl','fresh_target.png','returned_target.png','camera_pre.json','restoredA.json','restoredB.json']:
   shutil.copyfile(ROOT/n,self.root/n)
 def tearDown(self):self.tmp.cleanup()
 def runqa(self):return replay.run(self.root,6)
 def test_incomplete(self):
  q=self.runqa();self.assertEqual(q['status'],'INCOMPLETE_OR_REJECTED');self.assertEqual(q['present_brackets'],0);self.assertEqual(len(q['missing']),18);self.assertTrue(q['restoration']['camera_observed_stock_settings'])
 def test_duplicate_restore(self):
  shutil.copyfile(self.root/'restoredA.json',self.root/'restoredB.json');self.assertIsNone(self.runqa()['restoration'])
 def test_restore_zoom(self):
  p=self.root/'restoredB.json';q=json.loads(p.read_text());q['control.zoomRatio']='1.00000000';p.write_text(json.dumps(q));self.assertIsNone(self.runqa()['restoration'])
 def test_absent_restore(self):
  (self.root/'restoredB.json').unlink();self.assertIsNone(self.runqa()['restoration'])
 def test_target_settings(self):
  p=self.root/'log.jsonl';rows=[json.loads(l) for l in p.read_text().splitlines()]
  for row in rows:
   if row[1]=='target_after':row[2]=row[2].replace('screen_brightness=105','screen_brightness=106')
  p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertIsNone(self.runqa()['restoration'])
 def test_crop_corrupt(self):
  from PIL import Image
  p=self.root/'returned_target.png'
  with Image.open(p) as im:
   im=im.convert('RGB');r,g,b=im.getpixel((500,1000));im.putpixel((500,1000),((r+1)%256,g,b));im.save(p)
  self.assertIsNone(self.runqa()['restoration'])
 def test_reordered_return(self):
  p=self.root/'log.jsonl';rows=[json.loads(l) for l in p.read_text().splitlines()];rows.reverse();p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertIsNone(self.runqa()['restoration'])
if __name__=='__main__':unittest.main()
