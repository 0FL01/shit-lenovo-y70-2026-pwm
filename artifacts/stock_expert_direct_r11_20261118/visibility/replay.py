"""Offline known-A visibility diagnostic; no device access or geometric fitting."""
import argparse,hashlib,json,random
from pathlib import Path
import numpy as np
from PIL import Image
TRANSFORM=Path(__file__).resolve().parents[2]/'stock_direct_image_r10_20261118/analysis/locked_transform.json'
SHA='952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631'
NAMES=('expert_wide','short_drag','short2','short3','short4')
def code(seed=103820241):
 r=random.Random(seed);c=np.zeros((8,8))
 for row in c:row[r.sample(range(8),4)]=1
 return c*2-1
def geometry():
 raw=TRANSFORM.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('fixed R10 transform differs')
 z=json.loads(raw);x=np.array(z['sample_x']);y=np.array(z['sample_y']);th=np.array(z['thresholds'])[:,None];p=z['parameters'];ix=np.floor(x).astype(int);iy=np.floor(y).astype(int)
 X,Y=np.meshgrid(np.arange(900,1080),np.arange(910,1335));u,v=np.linalg.inv(np.array([[p[2],p[4]],[p[3],p[5]]]))@np.array([(X-p[0]).ravel(),(Y-p[1]).ravel()]);mask=((u>=0)&(u<8)&(v>=0)&(v<8)&(abs(u%1-.5)<=.2)&(abs(v%1-.5)<=.2)).reshape(X.shape)
 footprint=sorted(set((int(yy+dy),int(xx+dx)) for xx,yy in zip(ix.ravel(),iy.ravel()) for dx,dy in [(0,0),(1,0),(0,1),(1,1)]))
 return x,y,th,mask,np.array(footprint)
def stats(a):return dict(count=len(a),rgb_min=a.min(0).tolist(),rgb_max=a.max(0).tolist(),any255=int((a==255).any(1).sum()),zero_rgb=(a==0).sum(0).tolist(),all_zero=int((a==0).all(1).sum()))
def assess(a,c=None):
 if a.shape!=(2392,1080,3) or a.dtype!=np.uint8:raise ValueError('wrong RGB preview')
 if c is None:c=code()
 x,y,th,mask,fp=geometry();ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);dx=x-ix;dy=y-iy;g=a@np.array([.2126,.7152,.0722]);v=g[iy,ix]*(1-dx)*(1-dy)+g[iy,ix+1]*dx*(1-dy)+g[iy+1,ix]*(1-dx)*dy+g[iy+1,ix+1]*dx*dy;values=np.median(v,axis=0).reshape(8,8);vc=values-values.mean(1,keepdims=True);n=float((vc*c).sum()/max(1e-12,np.sqrt((vc*vc).sum()*64)));correct=int(((values>=th)==(c>0)).sum());contrast=float(np.median(values[c>0])-np.median(values[c<0]))
 return dict(original_threshold_correct=correct,row_centered_ncc=n,contrast=contrast,known_A_threshold_gate=correct>=60 and n>=.8 and contrast>=12,values=values.tolist(),central40_integer_centers=stats(a[910:1335,900:1080][mask]),bilinear_four_neighbor_union=stats(a[fp[:,0],fp[:,1]]),ordered_rows=sum(float(row[cc>0].min())>float(row[cc<0].max()) for row,cc in zip(values,c)))
def replay(root):
 paths=[root/(n+'.png') for n in NAMES];hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
 if len(set(hashes))!=len(paths):raise ValueError('duplicate source preview')
 out={}
 for name,p in zip(NAMES,paths):
  with Image.open(p) as im:
   if im.format!='PNG':raise ValueError('original PNG required')
   out[name]=assess(np.array(im.convert('RGB')))
 return dict(status='known_A_visibility_diagnostic_not_blind_validation',transform_sha=SHA,frames=out,limits=['Fixed R10 transform and absolute row thresholds, no fitting.','Only static known A; wrong-A negatives are diagnostic, not new heldout B.','1280 integer pixel centers inside central40% differs from2944 unique four-neighbor bilinear support pixels.','Neither support defines pixel-to-time calibration, kinematics, light linearity or PWM frequency.'])
def render(v):
 return '{\n'+',\n'.join('  '+json.dumps(k)+':'+json.dumps(x,separators=(',',':'),allow_nan=False) for k,x in v.items())+'\n}'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(render(replay(a.root)))
