"""Offline tests; manufactured visible fixtures using unrelated deterministic public codebook. Never load live keys/images."""
import hashlib,importlib.util,json,random,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
D=Path(__file__).resolve().parent
def mod(n):
 s=importlib.util.spec_from_file_location(n,D/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=mod('predict');S=mod('score')
def public_codebook():
 r=random.Random(123)
 def c():return [[1 if i in s else -1 for i in range(8)] for s in [set(r.sample(range(8),4)) for _ in range(8)]]
 return dict(C=c(),D=c(),order=list('CDUcdC'),salt='synthetic')
def ideal(d,key):
 ys,xs=np.mgrid[910:1335,900:1080];p=P.p
 uv=np.linalg.inv(np.array([[p[2],p[4]],[p[3],p[5]]]))@np.stack(((xs-p[0]).ravel(),(ys-p[1]).ravel()));u,v=np.floor(uv).astype(int).reshape(2,425,180)
 for i,phase in enumerate(key['order'],1):
  val=np.full((2392,1080),120,np.uint8)
  if phase!='U':val[910:1335,900:1080]=120+64*np.array(key[phase.upper()])[v%8,u%8]*(1 if phase.isupper() else -1)
  for j in range(1,4):
   val[0,0]=i*3+j; Image.fromarray(val).save(d/f'p{i:02d}_{j}.png',compress_level=1)
class Synthetic(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.root=Path(cls.tmp.name)
  cls.inp=cls.root/'frames';cls.inp.mkdir();cls.out=cls.root/'pred';cls.key=public_codebook();ideal(cls.inp,cls.key)
  cm=subprocess.run([sys.executable,'-P',str(D/'predict.py'),str(cls.inp),str(cls.out)],capture_output=True,text=True,check=True)
  assert cm.stdout.strip()==hashlib.sha256(cls.out.read_bytes()).hexdigest()
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def fresh(self):return json.loads(self.out.read_bytes())
 def test_complete_manifest(self):
  a=S.main(self.fresh(),self.key);self.assertTrue(a['decoder_pixel_pass']);self.assertEqual(len(a['inversions']),6);self.assertEqual(len(a['frames']),18)
 def test_single_bad_code_gap(self):
  f=self.fresh();f['p02_1.png']['gap']=11.999;self.assertFalse(S.main(f,self.key)['decoder_pixel_pass'])
 def test_nonzero_clipping(self):
  f=self.fresh();f['p02_1.png']['endpoints']=1;self.assertFalse(S.main(f,self.key)['decoder_pixel_pass'])
 def test_sham_structure(self):
  f=self.fresh();f['p03_1.png']['row_split']=12;self.assertFalse(S.main(f,self.key)['decoder_pixel_pass'])
 def test_correlated_sham(self):
  f=self.fresh();f['p03_1.png']['y']=f['p01_1.png']['y'];self.assertFalse(S.main(f,self.key)['decoder_pixel_pass'])
 def test_wrong_key_commit(self):
  with self.assertRaises(ValueError):S.verify(self.out,'0'*64)
 def test_wrong_mapping_rejected(self):
  k=dict(self.key);k['order']=list('DCUcdC');self.assertFalse(S.main(self.fresh(),k)['decoder_pixel_pass'])
 def test_refuse_overwrite(self):
  cm=subprocess.run([sys.executable,'-P',str(D/'predict.py'),str(self.inp),str(self.out)],capture_output=True,text=True);self.assertNotEqual(cm.returncode,0);self.assertIn('FileExistsError',cm.stderr)
if __name__=='__main__':unittest.main()
