"""No camera PNGs, user files, devices or live keys needed."""
import hashlib,importlib.util,json,unittest
from pathlib import Path
D=Path(__file__).resolve().parent
def get(name):return json.loads((D/name).read_bytes())
sp=importlib.util.spec_from_file_location('public_scorer',D/'score.py');sc=importlib.util.module_from_spec(sp);sp.loader.exec_module(sc)
class PublicReplay(unittest.TestCase):
 def test_exact(self):
  self.assertEqual(sc.main(get('preview_aggregates.json'),get('revealed_codes.json')),get('outcome.json'))
 def test_expected_gates(self):
  out=get('outcome.json');coded=[v for v in out['frames'].values() if 'ncc' in v];sham=[v for v in out['frames'].values() if 'null_abs_ncc' in v]
  self.assertEqual((len(coded),len(sham)),(15,3));self.assertFalse(out['decoder_pixel_pass'])
  self.assertEqual(sum(v['ok'] for v in coded),9);self.assertEqual(sum(v['gap']<12 for v in coded),6)
  self.assertEqual(sorted(v['endpoints'] for v in coded if v['endpoints']),[1,9])
  self.assertEqual(sum(v['accuracy'] for v in coded),954);self.assertTrue(all(v['ok'] for v in sham))
  self.assertTrue(all(v['ok'] for v in out['inversions'].values()));self.assertEqual(len(out['inversions']),6)
 def test_freeze(self):
  man=(D/'original_freeze.sha256').read_bytes();self.assertEqual(hashlib.sha256(man).hexdigest(),'5285639f7dccff76abab209a2c5280d5c4c42a1a6c8aabde2225a3098c88b35f')
  dig={n:h for h,n in (ln.split() for ln in man.decode().splitlines())}
  for n,p in [('SPEC.txt','SPEC.txt'),('operator.py','operator_plan.py'),('score.py','score.py')]:
   self.assertEqual(hashlib.sha256((D/p).read_bytes()).hexdigest(),dig[n])
if __name__=='__main__':unittest.main()
