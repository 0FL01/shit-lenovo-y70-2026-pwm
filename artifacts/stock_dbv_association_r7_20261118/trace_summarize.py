"""Summarize previously saved ordinal CSVs, then reveal fixed protocol labels.

No images, acquisition modules or device I/O. No Hz, independent-sample statistics,
physical calibration or causal inference. CSV parsing deliberately comes first.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np

LABELS=(2632,2632,2633,2632,2631,2632,2633,2634,2633,2632,2633,2633,2634,2633,2632,2631,2632)
VARIANTS=((18,0,0),(12,0,0),(24,0,0),(18,-3,0),(18,3,0),(18,0,-3),(18,0,3))
def stats(values):
    if not values:raise ValueError('missing comparison group')
    return dict(n=len(values),minimum=min(values),median=float(np.median(values)),maximum=max(values))

def summarize(path):
    with path.open(newline='') as f:rows=list(csv.DictReader(f))
    output={}
    for variant in VARIANTS:
        subset=[r for r in rows if tuple(int(r[k]) for k in ('threshold','dx','dy'))==variant]
        if len(subset)!=153:raise ValueError('requires all 17 complete ordinal blocks')
        seen=set();groups={k:[] for k in ('up','down','left_neighbor','right_neighbor','within','same_between')}
        lgroups={k:[] for k in groups}
        pairs=[]
        for r in subset:
            i,j=int(r['a'][1:]),int(r['b'][1:]); key=i,j
            if not 0<=i<=j<17 or key in seen:raise ValueError('duplicate/invalid ordinal pair')
            seen.add(key)
            if int(r['n'])!=(3 if i==j else 9):raise ValueError('pair count differs')
            a,b=LABELS[i],LABELS[j]
            if i==j:g='within'
            elif a==b:g='same_between'
            elif j==i+1 and {a,b}=={2632,2633}:g='up' if a<b else 'down'
            elif j==i+1 and {a,b}=={2631,2632}:g='left_neighbor'
            elif j==i+1 and {a,b}=={2633,2634}:g='right_neighbor'
            else:continue
            d,l=float(r['Dmed']),float(r['Lmed'])
            if not np.isfinite([d,l]).all():raise ValueError('nonfinite metric')
            groups[g].append(d);lgroups[g].append(l)
            pairs.append(dict(a=i,b=j,category=g,Dmed=d,Lmed=l))
        target=groups['up']+groups['down'];control=sum([groups[k] for k in ('left_neighbor','right_neighbor','within','same_between')],[])
        if len(target)!=6 or len(control)!=63:raise ValueError('wrong protocol partition')
        margin=min(target)-max(control)
        output[','.join(map(str,variant))]=dict(D={k:stats(v) for k,v in groups.items()},L={k:stats(v) for k,v in lgroups.items()},boundary=stats(target),control=stats(control),margin=margin,descriptive_separation=margin>0,comparisons=pairs)
    main=output['18,0,0']['descriptive_separation'];sensitivity=all(v['descriptive_separation']==main for v in output.values())
    return dict(primary_separates=main,sensitivity_agrees=sensitivity,variants=output,limits=['Fixed order, overlapping comparisons: not independent trials or a causal claim.','D is raster occupancy distribution, not frequency or calibrated amplitude.','Frozen comparison does not establish registration of the full scope screen.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ordinal_pairs',type=Path);p.add_argument('new_json',type=Path);a=p.parse_args()
    data=summarize(a.ordinal_pairs)
    with a.new_json.open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
