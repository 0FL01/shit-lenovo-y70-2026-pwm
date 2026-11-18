"""Unlock only after publishing prediction hash; no device access.
Usage: python3 score.py predictions.json key.json prior_pred_hash prior_key_hash output.json"""
from pathlib import Path
import sys,hashlib,json,random
import numpy as np
def verify(f,h):
 b=Path(f).read_bytes()
 if hashlib.sha256(b).hexdigest()!=h:raise ValueError('commitment mismatch')
 return json.loads(b)
def ncc(a,c):
 a=a-a.mean(1,keepdims=True);c=c-c.mean(1,keepdims=True);return float((a*c).sum()/max(1e-12,np.sqrt((a*a).sum()*(c*c).sum())))
def main(pred,key):
 order=key['order'];codes={k:np.array(key[k]) for k in 'CD'};codes.update(c=-codes['C'],d=-codes['D'])
 if sorted(order[:5])!=sorted('CcDdU') or order[5]!='C' or order[4]=='C':raise ValueError('order')
 if any(c.shape!=(8,8) or set(c.ravel())!={-1,1} or np.any(c.sum(1)) for c in codes.values()):raise ValueError('invalid key codes')
 rng=random.Random(20261118);decoys=[]
 for _ in range(99):
  m=np.full((8,8),-1)
  for row in m:row[rng.sample(range(8),4)]=1
  decoys.append(m)
 out={};pairs={};repeat={}; waves={}
 for i,label in enumerate(order,1):
  ys=[]
  for j in range(1,4):
   name=f'p{i:02d}_{j}.png';a=pred[name];y=np.array(a['y']);ys.append(y)
   met={k:a[k] for k in ['gap','endpoints','near_endpoints','row_split']}
   if label=='U':
    mx=max(abs(ncc(y,codes[k])) for k in 'CD');met.update(null_abs_ncc=mx,ok=bool(mx<.50 and a['row_split']<12 and a['endpoints']==0))
   else:
    c=codes[label];other='D' if label.upper()=='C' else 'C'
    t=ncc(y,c);md=max(ncc(y,e) for e in decoys+[-c,c.T,codes[other],-codes[other]]);accuracy=int((np.array(a['rank'])==c).sum());old=int((np.array(a['old'])==c).sum());contrast=float(np.median(y[c>0])-np.median(y[c<0]));met.update(accuracy=accuracy,old_absolute=old,ncc=t,contrast=contrast,max_decoy=md,margin=t-md,ok=bool(accuracy>=60 and t>=.8 and contrast>=12 and t-md>=.1 and a['gap']>=12 and a['endpoints']==0))
   out[name]=met
  ys=np.array(ys);ab=np.abs(ys-np.median(ys,axis=0));repeat[f'p{i:02d}']=dict(robust=float(1.4826*np.median(ab)),p95=float(np.quantile(ab,.95)),maximum=float(ab.max()))
  if label not in waves:waves[label]=ys
 for label in 'CD':
  deltas=(waves[label]-waves[label.lower()])*codes[label]
  for j,delta in enumerate(deltas,1):
   n=int((delta>0).sum());m=float(np.median(delta));pairs[label+str(j)]=dict(sign=n,median=m,ok=bool(n>=60 and m>=12))
 return dict(decoder_pixel_pass=all(v['ok'] for v in [*out.values(),*pairs.values()]),frames=out,inversions=pairs,phase_order=order,repeat=repeat)
if __name__=='__main__':
 ans=main(verify(sys.argv[1],sys.argv[3]),verify(sys.argv[2],sys.argv[4]))
 with Path(sys.argv[5]).open('x') as f:json.dump(ans,f,indent=2)
 print('decoder_pixel_pass',ans['decoder_pixel_pass'])
