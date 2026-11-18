"""Post-seal source and blinding-channel linkage; offline only."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image
KEY='6684bf87f9ef6de8c6d33a9b6118aabb988d6926facf4accd7616f2ea176d747'
PRED='c3c353e34585c4e4b4bc60d16586d813219bc1372a9a2714f23f09e3b1a56079'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def audit(root,blind,pred_file):
 r=Path(root);b=Path(blind);pdata=Path(pred_file).read_bytes();need(sha(pdata)==PRED,'prediction seal mismatch')
 key_data=(r/'private_pages/key.json').read_bytes();need(sha(key_data)==KEY,'key seal mismatch');k=json.loads(key_data)
 need(len(k['order'])==6 and k['order'][-1]=='C' and sorted(k['order'][:5])==sorted(['C','D','c','d','U']) and k['order'][4]!='C','roster')
 names={f'p{i:02}_{j}.png' for i in range(1,7) for j in range(1,4)};need(set(p.name for p in b.iterdir())==names,'decoder handoff extras/missing')
 out=[];hashes={};ys=332+np.floor((np.arange(48)+.5)*2758/48).astype(int);xs=30+60*np.arange(24)
 for i,s in enumerate(k['order']):
  lab=f'P{i:02d}';slug=f'p{i+1:02d}';html=(r/'private_pages'/(slug+'.html')).read_bytes();need(html==(r/(lab+'.html')).read_bytes(),'HTML not delivered')
  pts=re.findall(r'<rect x="(\d+)" y="(\d+)" width="60" height="60" fill="#b8b8b8"/>',html.decode())
  if s=='U':need(not pts and b'fill="#787878"' in html,'bad uniform HTML');val=np.full((8,8),120)
  else:
   code=np.array(k[s.upper()],dtype=int)*(1 if s.isupper() else -1)
   need(code.shape==(8,8) and np.all(np.abs(code)==1) and np.all(code.sum(1)==0),'bad key')
   pts2={(int(x),int(y)) for x,y in pts}
   need(pts2=={(x*60,y*60) for y in range(8) for x in range(8) if code[y,x]>0} and len(pts)==32,'wrong HTML pattern')
   val=np.where(code==1,184,56)
  expected=np.repeat(np.tile(val,(6,3))[:,:,None],3,axis=2)
  early=np.array(Image.open(r/(lab+'_source.png')).convert('RGB'));late=np.array(Image.open(r/(lab+'_last_source.png')).convert('RGB'))
  need(early.shape==late.shape==(3168,1440,3) and np.array_equal(early[np.ix_(ys,xs)],expected) and np.array_equal(early[332:3090],late[332:3090]),'source pixels differ')
  if s=='U':need(np.all(early[400:2800]==120),'nonuniform interior')
  roi=early[332:3090];row=roi.astype(np.int64).sum(axis=1);sums=row.sum(axis=0)
  out.append(dict(ordinal=slug,role=s,verified_centres=1152,early_late_plateau_equal=True,plateau_channel_sum=sums.tolist(),max_abs_row_delta_from_ideal=int(np.abs(row-172800).max())))
  for j in range(3):
   alias=slug+'_'+str(j+1)+'.png';source=lab+'_'+str(j)+'.png';h=sha((r/source).read_bytes());need(h==sha((b/alias).read_bytes()),'wrong blind alias');hashes[alias]=h
 need(len(set(hashes.values()))==18,'duplicate image')
 need(next(x for x in out[:-1] if x['role']=='C')['plateau_channel_sum']==out[-1]['plateau_channel_sum'],'return C budget drift')
 return dict(operator_key_commitment=KEY,blind_prediction_commitment=PRED,source=out,identical_18_input_aliases=True,sha256=hashes,limitations=['Static spatial source only, not equal optical brightness.','Android system bars excluded from source equality.','Prediction timestamp sequencing recorded by analyst/operator handoff; hashes verify bytes, not the mental state of participants.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('private');p.add_argument('blind');p.add_argument('sealed_predictions');a=p.parse_args();print(json.dumps(audit(a.private,a.blind,a.sealed_predictions),indent=2))
