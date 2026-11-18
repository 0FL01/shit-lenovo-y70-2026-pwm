"""Tests modify temporary copies, never the original camera PNGs."""
import unittest,sys,tempfile,shutil,subprocess,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(sys.argv.pop(1));SCRIPT=Path(__file__).with_name('replay.py')
class Replay(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.d=Path(self.temp.name)
  for n in ['A1','Ai','B','Bi','A2']:
   for i in (0,1):shutil.copyfile(ROOT/(n+str(i)+'.png'),self.d/(n+str(i)+'.png'))
 def tearDown(self):self.temp.cleanup()
 def run_replay(self):return subprocess.run([sys.executable,'-B',str(SCRIPT),str(self.d),'--require-pass'],capture_output=True,text=True)
 def test_original_all_ten(self):
  r=self.run_replay();self.assertEqual(r.returncode,0,r.stderr);v=json.loads(r.stdout)
  self.assertEqual(len(v['phases']),5)
  for p in v['phases'].values():
   self.assertEqual(len(p['frames']),2)
   for q in p['frames']+[p['mean']]:self.assertEqual(q['correct'],64);self.assertTrue(q['pass_'])
 def test_duplicate(self):
  shutil.copyfile(self.d/'A10.png',self.d/'A11.png');self.assertNotEqual(self.run_replay().returncode,0)
 def test_missing(self):
  (self.d/'A21.png').unlink();self.assertNotEqual(self.run_replay().returncode,0)
 def test_swap_independent_B_with_A(self):
  for a,b in [('A10.png','B0.png'),('A11.png','B1.png')]:
   x=(self.d/a).read_bytes();y=(self.d/b).read_bytes();(self.d/a).write_bytes(y);(self.d/b).write_bytes(x)
  self.assertNotEqual(self.run_replay().returncode,0)
 def test_swap_B_with_inverse(self):
  x=(self.d/'B0.png').read_bytes();y=(self.d/'Bi0.png').read_bytes();(self.d/'B0.png').write_bytes(y);(self.d/'Bi0.png').write_bytes(x);self.assertNotEqual(self.run_replay().returncode,0)
 def test_holdout_shift_no_refit(self):
  p=self.d/'B0.png';a=np.asarray(Image.open(p));Image.fromarray(np.roll(a,12,axis=1)).save(p);self.assertNotEqual(self.run_replay().returncode,0)
if __name__=='__main__':unittest.main()
