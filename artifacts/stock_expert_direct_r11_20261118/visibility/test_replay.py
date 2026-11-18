"""Offline tests on actual read-only images and in-memory mutations."""
import sys,unittest,json,tempfile,shutil
from pathlib import Path
import numpy as np
from PIL import Image
import replay
ROOT=Path(sys.argv.pop(1))
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.v=replay.replay(ROOT);cls.a=np.array(Image.open(ROOT/'short3.png').convert('RGB'))
 def test_exact_known_A_counts(self):
  self.assertEqual([v['original_threshold_correct'] for v in self.v['frames'].values()],[32,63,58,64,64])
 def test_short2_failure_preserved(self):
  self.assertFalse(self.v['frames']['short2']['known_A_threshold_gate']);self.assertEqual(self.v['frames']['short2']['original_threshold_correct'],58)
 def test_short3_pass_diagnostic_only(self):self.assertTrue(self.v['frames']['short3']['known_A_threshold_gate'])
 def test_wrong_A(self):self.assertFalse(replay.assess(self.a,replay.code(937015809))['known_A_threshold_gate'])
 def test_inverse_A(self):self.assertFalse(replay.assess(self.a,-replay.code())['known_A_threshold_gate'])
 def test_zero_image(self):self.assertFalse(replay.assess(np.zeros_like(self.a))['known_A_threshold_gate'])
 def test_geometry_shift_no_refit(self):self.assertFalse(replay.assess(np.roll(self.a,12,axis=1))['known_A_threshold_gate'])
 def test_support_denominators(self):
  for v in self.v['frames'].values():self.assertEqual(v['central40_integer_centers']['count'],1280);self.assertEqual(v['bilinear_four_neighbor_union']['count'],2944)
 def test_no_clipping_short_vs_auto(self):
  self.assertEqual(self.v['frames']['expert_wide']['bilinear_four_neighbor_union']['any255'],1535)
  for name in replay.NAMES[1:]:
   v=self.v['frames'][name]['bilinear_four_neighbor_union'];self.assertEqual(v['any255'],0);self.assertEqual(v['zero_rgb'],[0,0,0])
 def test_bad_dimensions(self):
  with self.assertRaises(ValueError):replay.assess(self.a[:100])
 def test_duplicate_sources(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   for name in replay.NAMES:shutil.copyfile(ROOT/'short3.png',p/(name+'.png'))
   with self.assertRaises(ValueError):replay.replay(p)
 def test_render_roundtrip(self):self.assertEqual(json.loads(replay.render(self.v)),self.v)
if __name__=='__main__':unittest.main()
