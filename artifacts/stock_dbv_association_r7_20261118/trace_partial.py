"""Descriptive 14-block prefix ONLY. Never evaluates the complete 17-block criterion."""
import argparse,csv,json,hashlib,re
from pathlib import Path
from datetime import datetime
import numpy as np
from trace_summarize import LABELS,VARIANTS,stats
HASHES={'ordinal_frames.csv':'26c18a1579689f004564b442f29a5e3b06af23e26b8002a3c257efe79ffb8065','ordinal_pairs.csv':'3358c8dae35dde1a415d628857c5356b138044950cdfd5af6ddce91a5576da1f'}
def read(p):return json.loads(p.read_text())
def utc(t):return datetime.fromisoformat(t).timestamp()
def run(src,orddir):
 for f,h in HASHES.items():
  if hashlib.sha256((orddir/f).read_bytes()).hexdigest()!=h:raise ValueError('ordinal-only result changed')
 with (orddir/'ordinal_pairs.csv').open() as f:rows=list(csv.DictReader(f))
 with (orddir/'ordinal_frames.csv').open() as f:frames=list(csv.DictReader(f))
 logs=[json.loads(s) for s in (src/'oc.log').read_text().splitlines()]
 def one(k):
  v=[r for r in logs if r[1]==k]
  if len(v)!=1:raise ValueError('missing/duplicate '+k)
  return v[0]
 samples=[];labels=[];times=[];corner=[]
 for i in range(14):
  name=f'P{i:02}';cmd=one(name+'_command');label=int(cmd[2][2]);labels.append(label)
  pre=one(name+'_pre')[2];late=one(name+'_late')[2]
  if not(int(pre[2]['DBV'])==int(late[0]['DBV'])==label==LABELS[i]):raise ValueError('mapping differs')
  for when in ('early','end'):
   raw=(src/(name+'_'+when+'_display.txt')).read_text()
   if f'\n{label}\n0\n' not in raw or 'vsyncRate=120.00 Hz' not in raw:raise ValueError('raw state differs')
  for j in range(3):
   tag=name+f'_s{j}';m=one(tag+'_manifest')[2];q=read(src/(tag+'_qc.json'))
   if set(m)-set(q)!={'phase','n','sample','elapsed_end'} or m['phase']!=i or m['sample']!=j or m['n']!=label or not 0<float(m['elapsed_end'])<33 or any(m.get(k)!=val for k,val in q.items()) or not(q['fixture']['geometry']['pass_exterior'] and q['fixture']['pass_original_upper_headroom'] and q['legend']['pass_similarity']):raise ValueError('unqualified sample')
   t=utc(q['raster_start']);samples.append(q);times.append(t)
   item={'block':name,'index':j,'label':label,'elapsed_from_first_s':t-utc(one('P00_s0_manifest')[2]['raster_start']),'command_to_png_start_s':t-utc(cmd[2][0]),'png_window_s':utc(q['raster_end'])-t,'corner_supported':q['corner_supported'],'clear_displacement':q['clear_displacement']}
   item.update({k:v['pos'] for k,v in q['blue']['anchors'].items()});corner.append(item)
 variants={}
 for v in VARIANTS:
  rr=[r for r in rows if tuple(int(r[k]) for k in ('threshold','dx','dy'))==v]
  if len(rr)!=105:raise ValueError('not complete 14-block ordinal pairs')
  g={k:[] for k in ['up','down','left_neighbor','right_neighbor','same_between','within']};pairs=[]
  for r in rr:
   i,j=int(r['a'][1:]),int(r['b'][1:]);a,b=labels[i],labels[j]
   if i==j:k='within'
   elif a==b:k='same_between'
   elif j==i+1 and {a,b}=={2632,2633}:k='up' if a<b else 'down'
   elif j==i+1 and {a,b}=={2631,2632}:k='left_neighbor'
   elif j==i+1 and {a,b}=={2633,2634}:k='right_neighbor'
   else:continue
   d=float(r['Dmed']);g[k].append(d);pairs.append(dict(a=i,b=j,category=k,Dmed=d,Lmed=float(r['Lmed'])))
  bd=[p for p in pairs if p['category'] in ('up','down')];ctrl=[p for p in pairs if p['category'] not in ('up','down')]
  variants[','.join(map(str,v))]={'groups':{k:stats(x) for k,x in g.items()},'observed_boundary':bd,'control_max_example':max(ctrl,key=lambda p:p['Dmed']),'observed_boundary_min_example':min(bd,key=lambda p:p['Dmed']),'observed_control_exceeds_observed_boundary':max(p['Dmed'] for p in ctrl)>min(p['Dmed'] for p in bd)}
 y=np.array([float(r['yellow_fraction']) for r in frames]);starts=np.array(times)
 return dict(status='descriptive_prefix_only',complete_phases=14,accepted_pngs=42,planned_phases=17,full_criterion='not_evaluated_incomplete',variants=variants,per_block_yellow_median=[float(np.median(y[i:i+3])) for i in range(0,42,3)],timing={'png_start_span_s':times[-1]-times[0],'png_gaps_s':stats(np.diff(starts).tolist()),'within_triplet_span_s':stats((starts[2::3]-starts[::3]).tolist()),'first_png_after_command_s':stats([r['command_to_png_start_s'] for r in corner[::3]]),'command_spacing_s':stats([utc(one(f'P{i:02}_command')[2][0])-utc(one(f'P{i-1:02}_command')[2][0]) for i in range(1,14)])},corner=corner,ordinal_only_sha256=HASHES,limits=['P14_s0 and all R frames excluded. No complete 17-phase criterion or power estimate.','Periodic readback and known order do not exclude time confounding.','Corner coordinates are a separate witness, not full rigid/perspective registration.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('src',type=Path);p.add_argument('ordinals',type=Path);p.add_argument('out',type=Path);a=p.parse_args();v=run(a.src,a.ordinals)
 with a.out.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
