"""Reconstruct private reference patches from hash-verified supplied R11 PNG."""
import argparse,hashlib,json,tempfile,io
from pathlib import Path
from contextlib import contextmanager
import numpy as np
import original_geometry as g
D=Path(__file__).resolve().parent
HASHES={'original_geometry.py':'9fec33994c4f46e773f58f6099c99365f6b79179e85ff3dfc575bc866adc9c28','freeze.json':'9dbee9c74ab13379155516aebcb855adc676b9c7ca47fe2f58db4edff30d4aa8','locked_transform.json':'952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631'}
@contextmanager
def reference(source):
 for name,h in HASHES.items():
  if hashlib.sha256((D/name).read_bytes()).hexdigest()!=h:raise ValueError('frozen source differs: '+name)
 f=json.loads((D/'freeze.json').read_text())
 if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=f['reference_sha256']:raise ValueError('wrong archived reference PNG')
 a=g.load(source)
 with tempfile.TemporaryDirectory(prefix='r12-reference-') as temp:
  t=Path(temp)
  for name in ['freeze.json','locked_transform.json']:(t/name).write_bytes((D/name).read_bytes())
  for i,(x,y,X,Y) in enumerate(f['boxes']):
   b=io.BytesIO();np.save(b,a[y:Y,x:X],allow_pickle=False);raw=b.getvalue();name=f'template{i}.npy'
   if hashlib.sha256(raw).hexdigest()!=f['files'][name]:raise ValueError('reconstructed template hash differs')
   (t/name).write_bytes(raw)
  previous=g.D;g.D=t
  try:yield g
  finally:g.D=previous

def replay(source,images):
 with reference(source) as module:
  return [dict(name=Path(p).name,checks=module.checks(module.load(p))) for p in images]
def render(value):return json.dumps(value,indent=2)+'\n'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path);p.add_argument('images',nargs='+',type=Path);args=p.parse_args();print(render(replay(args.reference,args.images)),end='')
