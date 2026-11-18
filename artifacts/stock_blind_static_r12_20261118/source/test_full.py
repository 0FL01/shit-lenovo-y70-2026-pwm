"""Operator-only R12b negative tests; never reads assignment or HTML."""
import sys,tempfile,json,shutil,unittest
from pathlib import Path
import replay
ROOT=Path(sys.argv.pop(1))
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  names=['log.jsonl','fresh_target.png','returned_target.png','camera_pre.json','restoredA.json','restoredB.json']
  for i in range(6):
   p=f'P{i:02d}';names += [p+'_early.json',p+'_late.json',p+'_source.png',p+'_last_source.png']
   for j in range(3):names += [p+f'_{j}'+s for s in ['.png','_pre_raw.txt','_post_raw.txt','_pre_metadata.json','_post_metadata.json']]
  for n in names:shutil.copyfile(ROOT/n,self.root/n)
 def tearDown(self):self.tmp.cleanup()
 def qa(self,e='156250'):return replay.run(self.root,6,e)
 def test_full_actual(self):
  q=self.qa();self.assertEqual(q['status'],'SPEC_ACTUAL_PASS_R11_REQUEST_FAIL');self.assertEqual(q['present_brackets'],18);self.assertEqual(q['unique_png_hashes'],18);self.assertFalse(q['frozen_R11_request_matches']);self.assertFalse(q['failures'])
 def test_frozen_request_reject(self):self.assertEqual(self.qa('200000')['present_brackets'],0)
 def test_actual_corruption(self):
  p=self.root/'P00_0_pre_raw.txt';p.write_text(p.read_text().replace('[156000 ]','[157000 ]',1));self.assertEqual(self.qa()['present_brackets'],17)
 def test_duplicate_png(self):
  shutil.copyfile(self.root/'P00_0.png',self.root/'P00_1.png');self.assertEqual(self.qa()['status'],'INCOMPLETE_OR_REJECTED')
 def test_missing(self):
  (self.root/'P05_2_post_raw.txt').unlink();self.assertEqual(len(self.qa()['missing']),1)
 def test_duplicate_restore(self):
  shutil.copyfile(self.root/'restoredA.json',self.root/'restoredB.json');self.assertIsNone(self.qa()['restoration'])
 def test_json_identity(self):
  p=self.root/'P00_0_pre_metadata.json';q=json.loads(p.read_text());q['request.frameCount']='0';p.write_text(json.dumps(q));self.assertEqual(self.qa()['present_brackets'],17)
 def test_bracket_receipt(self):
  p=self.root/'log.jsonl';rows=[json.loads(l) for l in p.read_text().splitlines()]
  for row in rows:
   if row[1]=='P00_0_bracket':row[2][0][0]=0
  p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertEqual(self.qa()['status'],'INCOMPLETE_OR_REJECTED')
if __name__=='__main__':unittest.main()
