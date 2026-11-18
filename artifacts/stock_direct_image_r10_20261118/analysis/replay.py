import json,random,hashlib,argparse,sys
from pathlib import Path
import numpy as np
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--require-pass',action='store_true');args=p.parse_args();D=args.root
raw=(Path(__file__).parent/'locked_transform.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!='952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631':raise ValueError('frozen transform changed')
locked=json.loads(raw);files=[D/(name+str(i)+'.png') for name in ['A1','Ai','B','Bi','A2'] for i in (0,1)]
if any(not f.is_file() for f in files):raise ValueError('incomplete ten-frame sequence')
if len(set(hashlib.sha256(f.read_bytes()).hexdigest() for f in files))!=10:raise ValueError('duplicated raw frame')
locked=json.loads(raw);x=np.array(locked['sample_x']);y=np.array(locked['sample_y']);th=np.array(locked['thresholds'])[:,None]
def code(seed):
 r=random.Random(seed);a=np.zeros((8,8))
 for row in a:row[r.sample(range(8),4)]=1
 return a*2-1
A=code(103820241);B=code(937015809);rng=random.Random(20261118);decoys=[]
for k in range(99):
 c=np.zeros((8,8))
 for row in c:row[rng.sample(range(8),4)]=1
 decoys.append(c*2-1)
def extract(im):
 ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);dx=x-ix;dy=y-iy
 v=im[iy,ix]*(1-dx)*(1-dy)+im[iy,ix+1]*dx*(1-dy)+im[iy+1,ix]*(1-dx)*dy+im[iy+1,ix+1]*dx*dy
 return np.median(v,axis=0).reshape(8,8)
def ncc(v,c):
 v=v-v.mean(1,keepdims=True);c=c-c.mean(1,keepdims=True)
 return float((v*c).sum()/max(1e-9,np.sqrt((v*v).sum()*(c*c).sum())))
def assess(v,c):
 corr=ncc(v,c);ds=[ncc(v,z) for z in decoys]+[ncc(v,-c),ncc(v,c.T)]
 correct=int(((v>=th)==(c==1)).sum());contrast=float(np.median(v[c==1])-np.median(v[c==-1]));margin=corr-max(ds)
 return dict(correct=correct,ncc=corr,contrast=contrast,max_decoy=max(ds),specificity_margin=margin,pass_=correct>=60 and corr>=.8 and contrast>=12 and margin>=.1,cell_values=v.tolist())
results={};vals={}
for name,c in [('A1',A),('Ai',-A),('B',B),('Bi',-B),('A2',A)]:
 files=[D/(name+str(i)+'.png') for i in (0,1)]
 if not all(p.exists() for p in files):results[name]={'not_acquired_yet':True};continue
 ims=[np.asarray(Image.open(p).convert('RGB'),float)@np.array([.2126,.7152,.0722]) for p in files];v=[extract(im) for im in ims];m=extract(np.mean(ims,axis=0));vals[name]=v+[m];results[name]={'frames':[assess(z,c) for z in v],'mean':assess(m,c)}
pairs={}
for a,b,c in [('A1','Ai',A),('B','Bi',B)]:
 if a not in vals or b not in vals:continue
 out=[]
 for va,vb in zip(vals[a],vals[b]):
  signed=(va-vb)*c;n=int((signed>0).sum());med=float(np.median(signed));out.append(dict(correct_sign=n,median_signed_change=med,pass_=n>=60 and med>=12))
 pairs[a+'_'+b]=out
out=dict(locked_transform_sha='952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631',phases=results,inversions=pairs,limits=['Specificity decoys only at fixed A-selected geometry, not corrected for search.','Two sequential frames per phase, no generalizability, linearity, PWM or causal physical metrology.'])
print(json.dumps(out,indent=2,allow_nan=False))
passed=all(v['mean']['pass_'] and all(z['pass_'] for z in v['frames']) for v in results.values()) and len(results)==5 and all(z['pass_'] for v in pairs.values() for z in v) and len(pairs)==2
if args.require_pass and not passed:raise SystemExit(2)
