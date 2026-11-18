"""Frozen local-structure translation witness, not full display registration."""
from pathlib import Path
import hashlib,json,argparse
import numpy as np
from PIL import Image
D=Path(__file__).resolve().parent
def load(p):
 with Image.open(p) as im:a=np.array(im.convert('RGB'))
 if a.shape!=(2392,1080,3):raise ValueError('wrong preview dimensions')
 return a
def ncc(a,b):
 a=a.astype(float).mean(2);b=b.astype(float).mean(2);a-=a.mean();b-=b.mean()
 return float((a*b).sum()/max(1e-9,np.linalg.norm(a)*np.linalg.norm(b)))
def checks(a):
 if a.shape!=(2392,1080,3) or a.dtype!=np.uint8:raise ValueError('wrong RGB preview')
 f=json.loads((D/'freeze.json').read_text())
 for name,h in f['files'].items():
  if hashlib.sha256((D/name).read_bytes()).hexdigest()!=h:raise ValueError('frozen dependency differs')
 out=[]
 for i,(x,y,X,Y) in enumerate(f['boxes']):
  t=np.load(D/f'template{i}.npy',allow_pickle=False)
  s=sorted([(ncc(t,a[y+dy:Y+dy,x+dx:X+dx]),dx,dy) for dy in range(-6,7) for dx in range(-6,7)],reverse=True)
  q,dx,dy=s[0];out.append(dict(ncc=q,dx=dx,dy=dy,pass_local=q>=.90 and max(abs(dx),abs(dy))<=2))
 z=json.loads((D/'locked_transform.json').read_text());ix=np.floor(z['sample_x']).astype(int);iy=np.floor(z['sample_y']).astype(int)
 fp=np.array(sorted(set((int(yy+dy),int(xx+dx)) for xx,yy in zip(ix.ravel(),iy.ravel()) for dx,dy in [(0,0),(1,0),(0,1),(1,1)])))
 p=a[fp[:,0],fp[:,1]];head=bool(p.max()<250)
 return dict(local_structures=out,pass_local_translation=all(q['pass_local'] for q in out),support_count=len(p),rgb_min=p.min(0).tolist(),rgb_max=p.max(0).tolist(),zero_per_channel=(p==0).sum(0).tolist(),any_zero=int((p==0).any(1).sum()),pass_headroom=head,pass_witness=all(q['pass_local'] for q in out) and head,full_display_registration='unknown')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('images',nargs='+');args=p.parse_args();print(json.dumps([dict(name=Path(n).name,checks=checks(load(n))) for n in args.images],indent=2))
