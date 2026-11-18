import numpy as np,random,json,time,argparse
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args();D=args.root
r=random.Random(103820241);code=np.zeros((8,8));
for row in code:row[r.sample(range(8),4)]=1
code=code*2-1
frames=[np.asarray(Image.open(D/n).convert('RGB'),float)@np.array([.2126,.7152,.0722]) for n in ['A10.png','A11.png']];im=np.mean(frames,axis=0)
u,v=np.meshgrid(np.arange(8)+.5,np.arange(8)+.5);u=u.ravel();v=v.ravel()
def sample(x,y):
 ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);dx=x-ix;dy=y-iy
 return im[iy,ix]*(1-dx)*(1-dy)+im[iy,ix+1]*dx*(1-dy)+im[iy+1,ix]*(1-dx)*dy+im[iy+1,ix+1]*dx*dy
best=[];X,Y=np.meshgrid(np.arange(900,1015,3),np.arange(955,1240,3));xy=np.column_stack([X.ravel(),Y.ravel()])
for sx in range(8,19,2):
 for sy in range(8,23,2):
  for vx in [-2.,-1.,0.]:
   for uy in [0.,1.,2.]:
    x=xy[:,0,None]+sx*u+vx*v;y=xy[:,1,None]+uy*u+sy*v
    ok=(x.min(1)>=901)&(x.max(1)<=1078)&(y.min(1)>=911)&(y.max(1)<=1333)
    if not ok.any():continue
    vals=sample(x[ok],y[ok]).reshape(-1,8,8);c=vals-vals.mean(2,keepdims=True)
    n=(c*code).sum((1,2))/np.maximum(1,np.sqrt((c*c).sum((1,2))*64))
    for i in np.flatnonzero(n>=.80):best.append((float(n[i]),list(map(float,[*xy[ok][i],sx,uy,vx,sy]))))
best=sorted(best,reverse=True);print(json.dumps(best,indent=2,allow_nan=False))
