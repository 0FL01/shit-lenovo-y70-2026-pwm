"""Offline independent four-zone replay on the exact observed incomplete R7 set."""
import argparse,json,re
from pathlib import Path
from collections import defaultdict
from corner_check import geom

def native(p):
 s=p.read_text();m=re.search(r'\n(263[1-4])\n0\n',s)
 if not m:raise ValueError('unconfirmed native plateau')
 return int(m[1])

def replay(root):
 names=['R%02d'%i for i in range(3)]+['P%02d_s%d'%(i,j) for i in range(14) for j in range(3)]+['P14_s0']
 rows=[];counts=defaultdict(lambda:dict(supported=0,unknown=0))
 for name in names:
  im=geom.load(root/(name+'.png'));blue=geom.score(im);q=json.loads((root/(name+'_qc.json')).read_text())
  if blue!=q['blue']:raise ValueError('raw blue score mismatch')
  r=blue['anchors'];supported=True;displaced=[]
  for a,b,n in [('top-right/a','top-right/b',963),('right-upper/a','right-upper/b',554)]:
   x,y=r[a],r[b]
   shape=lambda z:z['height']>=10 and z['grad']>=5 and 1<=z['width']<=6
   readable=shape(x) and shape(y) and abs(x['pos']-y['pos'])<=1
   supported &= readable and max(abs(x['pos']-n),abs(y['pos']-n))<=2
   if readable and (min(x['pos'],y['pos'])>n+2 or max(x['pos'],y['pos'])<n-2):displaced.append(a+'/'+b)
  if bool(supported)!=q['corner_supported'] or displaced!=q['clear_displacement']:raise ValueError('recorded corner mismatch')
  phase=name.split('_')[0] if name.startswith('P') else None
  code=native(root/((phase+'_early_display.txt') if phase else 'commission_entry_display.txt'))
  subset='rejected' if name=='P14_s0' else ('reference' if name.startswith('R') else 'accepted')
  if subset!='rejected':
   after=native(root/((phase+'_end_display.txt') if phase else 'commission_end_display.txt'))
   if after!=code:raise ValueError('late code mismatch')
  fields={k:r[k] for k in ('top-right/a','top-right/b','right-upper/a','right-upper/b')}
  row=dict(ordinal=name,subset=subset,native=code,native_after_verified=subset!='rejected',corner_supported=bool(supported),clear_displacement=displaced,anchors=fields)
  rows.append(row);counts[subset+'/'+str(code)]['supported' if supported else 'unknown']+=1
 rejected=json.loads((root/'P14_s0_qc.json').read_text())
 return dict(status='partial_r7_corner_and_labels_audit',scope='3 references + 42 accepted + 1 rejected; no P14_s1/s2,P15 or P16',counts=dict(counts),rows=rows,rejected_semantics={k:v for k,v in rejected['legend']['glyphs'].items() if not v['ok']},limits=['A human-readable legend never rehabilitates an automated semantic rejection.','supported is a four-zone diagnostic, not full-frame registration.','Rejected P14_s0 only has a preceding native readback, no late plateau closure.'])

def render(v):
 return json.dumps({k:x for k,x in v.items() if k!='rows'},indent=2)[:-2]+',\n  "rows":[\n'+',\n'.join('    '+json.dumps(x,separators=(',',':')) for x in v['rows'])+'\n  ]\n}'
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(render(replay(a.root)))
