"""Private independent offline negative checks on temporary copies only."""
import unittest,tempfile,shutil,json,sys
from pathlib import Path
from PIL import Image
import replay as qa
ORIG=Path(sys.argv.pop(1));qa.ROOT=ORIG
class Checks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();qa.ROOT=Path(self.temp.name)
  for p in ORIG.iterdir():
   if p.suffix in ('.png','.json','.jsonl','.html','.txt'):shutil.copyfile(p,qa.ROOT/p.name)
 def tearDown(self):qa.ROOT=ORIG;self.temp.cleanup()
 def reject(self):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError)):qa.audit()
 def test_complete(self):
  x=qa.audit();self.assertEqual(x['status'],'acquisition_complete_return_confirmed');self.assertEqual(len(x['phases']),5)
  self.assertEqual(x['budget_comparisons']['B']['max_abs_row_difference_vs_A1'],16740)
  self.assertEqual(x['budget_comparisons']['A2']['regions']['pattern_plateau']['different_pixels_vs_A1'],0)
 def test_pixel_code(self):
  p=qa.ROOT/'A1_target.png';im=Image.open(p).convert('RGB');im.putpixel((30,360),(0,0,0));im.save(p);self.reject()
 def test_html(self):
  p=qa.ROOT/'B.html';p.write_text(p.read_text().replace('fill="#b8b8b8"','fill="#ffffff"',1));self.reject()
 def test_wrong_native(self):
  p=qa.ROOT/'log.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
  for r in rows:
   if r[1]=='Ai_end':r[2]=r[2].replace('panel_brightness=828','panel_brightness=2632')
  p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.reject()
 def test_camera_restore(self):
  p=qa.ROOT/'stock_final2.json';m=json.loads(p.read_text());m['control.zoomRatio']='1.00000000';p.write_text(json.dumps(m));self.reject()
 def test_camera_duplicates(self):
  shutil.copyfile(qa.ROOT/'A10pre.json',qa.ROOT/'A10post.json');self.reject()
 def test_return_pending(self):
  p=qa.ROOT/'log.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()];rows=[r for r in rows if r[1] not in ['target_restored','camera_restored']];p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
  self.assertEqual(qa.audit()['status'],'acquisition_complete_return_pending')
 def test_missing_frame_is_partial(self):
  (qa.ROOT/'A21post.json').unlink();self.assertEqual(qa.audit()['status'],'partial')
 def test_release_float(self):
  p=qa.ROOT/'readback_release.txt';p.write_text(p.read_text().replace('mCurrentScreenBrightness=0.40987244','mCurrentScreenBrightness=0.5'));self.reject()
 def test_false_restore_receipt(self):
  p=qa.ROOT/'log.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
  next(r for r in rows if r[1]=='target_restored')[2][1]=['828','DIM']
  p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.reject()
 def test_reordered_event(self):
  p=qa.ROOT/'log.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
  i=next(i for i,r in enumerate(rows) if r[1]=='A1_end');j=next(i for i,r in enumerate(rows) if r[1]=='A10_bracket');rows[i],rows[j]=rows[j],rows[i]
  p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.reject()
if __name__=='__main__':unittest.main()
