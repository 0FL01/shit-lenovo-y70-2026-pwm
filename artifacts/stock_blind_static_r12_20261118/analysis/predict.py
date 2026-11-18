"""Blind decode only; no key/targets; writes new file. Usage: python3 predict.py previews output.json"""
from pathlib import Path
import sys,hashlib,json
import numpy as np
from PIL import Image
def sha(b):return hashlib.sha256(b).hexdigest()
T=(Path(__file__).resolve().parents[2]/'stock_direct_image_r10_20261118/analysis/locked_transform.json');z=T.read_bytes()
if sha(z)!='952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631':raise ValueError('geometry digest')
z=json.loads(z);x=np.array(z['sample_x']);y=np.array(z['sample_y']);p=z['parameters'];ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);dx=x-ix;dy=y-iy
X,Y=np.meshgrid(np.arange(900,1080),np.arange(910,1335));u,v=np.linalg.inv(np.array([[p[2],p[4]],[p[3],p[5]]]))@np.stack(((X-p[0]).ravel(),(Y-p[1]).ravel()));mask=((u>=0)&(u<8)&(v>=0)&(v<8)&(abs(u%1-.5)<=.2)&(abs(v%1-.5)<=.2)).reshape(X.shape)
if mask.sum()!=1280:raise ValueError('mask')
def extract(f):
 import io
 b=f.read_bytes();im=Image.open(io.BytesIO(b))
 if im.size!=(1080,2392) or im.format!='PNG':raise ValueError('dimensions/format: '+f.name)
 a=np.asarray(im.convert('RGB'));s=a[910:1335,900:1080][mask];rgb=np.stack([a[iy,ix],a[iy,ix+1],a[iy+1,ix],a[iy+1,ix+1]]);wt=np.stack([(1-dx)*(1-dy),dx*(1-dy),(1-dx)*dy,dx*dy]);vv=(rgb*wt[:,:,:,None]).sum(0)
 val=np.median(vv@np.array([.2126,.7152,.0722]),axis=0).reshape(8,8);ys=np.sort(val,axis=1);idx=np.argsort(val,axis=1,kind='stable')[:,4:];pred=np.full((8,8),-1);np.put_along_axis(pred,idx,1,axis=1)
 return dict(hash=sha(b),rank=pred.tolist(),y=val.tolist(),rgb=np.median(vv,axis=0).reshape(8,8,3).tolist(),old=(2*(val>=np.array(z['thresholds'])[:,None]).astype(int)-1).tolist(),gap=float(min(ys[:,4]-ys[:,3])),endpoints=int(np.any((s==0)|(s==255),axis=1).sum()),near_endpoints=int(np.any((s<=3)|(s>=252),axis=1).sum()),row_split=float(np.median(ys[:,4:].mean(1)-ys[:,:4].mean(1))))
if __name__=='__main__':
 d=Path(sys.argv[1]);f=Path(sys.argv[2]);names=[f'p{i:02d}_{j}.png' for i in range(1,7) for j in range(1,4)]
 if sorted(v.name for v in d.iterdir())!=names:raise ValueError('exactly 18 blind inputs required')
 out={n:extract(d/n) for n in names}
 if len(set(v['hash'] for v in out.values()))!=18:raise ValueError('duplicate source bytes')
 b=(json.dumps(out,sort_keys=True)+'\n').encode()
 with f.open('xb') as fp:fp.write(b)
 print(sha(b))
