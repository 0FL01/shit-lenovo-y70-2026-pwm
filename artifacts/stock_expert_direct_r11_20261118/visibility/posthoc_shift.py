"""Posthoc translation diagnostic. Does not change frozen-transform decisions."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
from replay import geometry,code

def run(root):
 x,y,_,_,_=geometry();c=code();out={}
 for name in ('short_drag','short2','short3','short4'):
  a=np.array(Image.open(root/(name+'.png')).convert('RGB'));g=a@np.array([.2126,.7152,.0722]);rows=[]
  for sx in np.arange(-3,3.01,.5):
   for sy in np.arange(-3,3.01,.5):
    xx=x+sx;yy=y+sy;ix=np.floor(xx).astype(int);iy=np.floor(yy).astype(int);dx=xx-ix;dy=yy-iy
    vv=g[iy,ix]*(1-dx)*(1-dy)+g[iy,ix+1]*dx*(1-dy)+g[iy+1,ix]*(1-dx)*dy+g[iy+1,ix+1]*dx*dy;v=np.median(vv,axis=0).reshape(8,8);v=v-v.mean(1,keepdims=True);score=float((v*c).sum()/max(1e-12,np.sqrt((v*v).sum()*64)));rows.append((score,float(sx),float(sy)))
  n,xs,ys=max(rows);out[name]=dict(ncc=n,dx=xs,dy=ys,search_boundary_hit=abs(xs)==3 or abs(ys)==3)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(json.dumps(run(a.root),indent=2))
