"""Archive-only: independent cell sampler and integer histogram distance."""
import argparse
import csv
from datetime import datetime
from hashlib import sha256
from itertools import combinations_with_replacement, combinations, product
import json
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image

A = Path(__file__).resolve().parents[1]
R12 = A/'stock_blind_static_r12_20261118'
R7 = A/'stock_dbv_association_r7_20261118'
SHAM = A/'stock_dbv_2632_badge_sham_20261118'
ORDER = (2632,2632,2633,2632,2631,2632,2633,2634,2633,2632,2633,2633,2634,2633,2632,2631,2632)
VARS = ((18,0,0),(12,0,0),(24,0,0),(18,-3,0),(18,3,0),(18,0,-3),(18,0,3))
AXES = ((1,0),(-1,0),(0,1),(0,-1))


def need(ok, why):
    if not ok:
        raise ValueError(why)


def read(p):
    return json.loads(p.read_bytes())


def rgb(p):
    with Image.open(p) as im:
        need(im.size == (1080,2392) and im.format == 'PNG', 'framing or file format')
        return np.array(im.convert('RGB'))


def signs(vals):
    need(vals.shape == (8,8), 'need 8x8')
    pos = np.argsort(vals, axis=1, kind='stable')[:,4:]
    pred = np.full((8,8), -1)
    np.put_along_axis(pred, pos, 1, axis=1)
    return pred


def centres(p):
    x,y,ux,uy,vx,vy = p
    v,u = np.mgrid[0:8,0:8] + 0.5
    return tuple(np.floor(a+.5).astype(int) for a in (x+ux*u+vx*v,y+uy*u+vy*v))


def sample(g, x, y):
    need(x.min()>=1 and y.min()>=1 and x.max()+1<g.shape[1] and y.max()+1<g.shape[0], 'sample outside PNG')
    return np.median(np.stack([g[y+j,x+i] for i,j in product((-1,0,1),repeat=2)]), axis=0)


def codes(src):
    source = read(R12/'source/outcome_r12b.json')
    bindings = {r['ordinal']:r['image']['sha256'] for r in source['frames']}
    transform = read(A/'stock_direct_image_r10_20261118/analysis/locked_transform.json')
    x,y = centres(transform['parameters'])
    names = [f'p{i+1:02d}_{j+1}.png' for i,j in product(range(6),range(3))]
    need(sorted(f.name for f in src.glob('*.png'))==names, 'incorrect R12b PNG set')
    shifts = [(0,0)]+[(r*dx,r*dy) for dx,dy in AXES for r in range(1,13)]
    preds = {s:[] for s in shifts}
    contrasts = []
    for i,name in enumerate(names):
        f = src/name
        need(sha256(f.read_bytes()).hexdigest()==bindings[f'P{i//3:02d}_{i%3}'], 'R12b image binding')
        green = rgb(f)[:,:,1]
        for dx,dy in shifts:
            vals = sample(green,x+dx,y+dy)
            preds[(dx,dy)].append(signs(vals))
            if dx==dy==0:
                row = np.sort(vals,axis=1)
                contrasts.append(float(np.median(row[:,4:].mean(1)-row[:,:4].mean(1))))
    key = read(R12/'analysis/revealed_codes.json')
    phases = [lab for lab in key['order'] for _ in range(3)]
    idx = [i for i,lab in enumerate(phases) if lab!='U']
    truth = np.array([np.array(key[phases[i].upper()])*(1 if phases[i].isupper() else -1) for i in idx])
    need(truth.shape==(15,8,8) and np.all((truth==1)|(truth==-1)), 'R12b key')
    bright = (truth==1).sum(0)
    bound = int(np.maximum(bright,len(idx)-bright).sum())
    scores = {s:(np.array(seq)[idx]==truth).sum((1,2)).tolist() for s,seq in preds.items()}
    scans = {}
    for dx,dy in AXES:
        totals = [sum(scores[(dx*r,dy*r)]) for r in range(1,13)]
        scans[str((dx,dy))] = dict(totals=totals,first_failure=next((i+1 for i,n in enumerate(totals) if n<=bound),None))
    return (dict(coded={names[i]:s for i,s in zip(idx,scores[(0,0)])},total=sum(scores[(0,0)]),
                 fixed_bound=bound,uniform_row_split_green=[contrasts[i] for i in range(18) if i not in idx]),scans)


def hist(mask):
    counts = mask.sum(axis=0)
    return np.bincount(counts,minlength=mask.shape[0]+1).cumsum()[:-1]


def descriptor(a,v):
    threshold,dx,dy = v
    rr,gg,bb = np.moveaxis(a[1150+dy:1240+dy,112+dx:540+dx].astype(np.int16),-1,0)
    return hist(rr+gg-2*bb>2*threshold)


def group(i,j):
    if i==j: return 'within'
    a,b=ORDER[i],ORDER[j]
    if a==b: return 'same'
    if j!=i+1: return None
    return 'cross' if {a,b}=={2632,2633} else 'neighbor'


def dvalues(data,i,j):
    inds = combinations(range(3),2) if i==j else product(range(3),repeat=2)
    # Sum of differences of cumulative multiplicities is equal to L1 distance
    # between sorted column counts. Each increment is one detector pixel.
    return [int(np.abs(data[i][s]-data[j][t]).sum()) for s,t in inds]


def summary(data, phases):
    entries = [(median(dvalues(data,i,j)),i,j,group(i,j)) for i,j in combinations_with_replacement(phases,2) if group(i,j)]
    target = [r for r in entries if r[3]=='cross']
    controls = [r for r in entries if r[3]!='cross']
    need(target and controls, 'insufficient complete phases')
    worst,best = min(target), max(controls)
    def encode(r):
        return dict(pair=list(r[1:3]),kind=r[3],d=round(r[0]/38520,9))
    return dict(n_cross=len(target),n_control=len(controls),min_cross=encode(worst),max_cross=encode(max(target)),
                max_control=encode(best),max_same=encode(max(r for r in controls if r[3]=='same')) if any(r[3]=='same' for r in controls) else None,
                margin=round((worst[0]-best[0])/38520,9),separated=worst[0]>best[0])


def original_checks(a,fixture):
    area = a[1080:1270,112:540]
    need(fixture['trace_pixels']==area.shape[0]*area.shape[1] and
         fixture['trace_zero_rgb']==(area==0).sum((0,1)).tolist() and fixture['trace_max']==int(area.max()),'raster receipt mismatch')


def r7(src):
    names = [f'P{i:02d}_s{j}' for i,j in product(range(14),range(3))]+['P14_s0']
    need(sorted(p.stem for p in src.glob('P*_s*.png'))==names,'unexpected R7 PNG set')
    entries = [json.loads(s) for s in (src/'oc.log').read_text().splitlines()]
    log = {k:v for _,k,v in entries if k.startswith('P')}
    need(len(log)==sum(k.startswith('P') for _,k,_ in entries),'duplicate R7 event')
    stack = {v:{i:[] for i in range(14)} for v in VARS}
    for i in range(15):
        p=f'P{i:02d}'
        pre=log[p+'_pre']
        need(log[p+'_command'][2]==pre[0]==pre[1]==int(pre[2]['DBV'])==ORDER[i], 'early DBV')
        if i<14:
            late=log[p+'_late']
            need(late[1]==int(late[0]['DBV'])==ORDER[i], 'late DBV')
    need(all(f'P{i:02d}_late' not in log for i in range(14,17)),'unexpected late completion')
    for k,name in enumerate(names):
        q=read(src/(name+'_qc.json'));a=rgb(src/(name+'.png'))
        need(q==log[name+'_qc'] and q['tag']==name,'R7 QC provenance')
        original_checks(a,q['fixture'])
        if k==42:
            failed={g:round(d['ncc'],6) for g,d in q['legend']['glyphs'].items() if not d['ok']}
            need(not q['legend']['pass_similarity'] and set(failed)=={'X1','AUTO'}, 'rejected case')
            continue
        need(q['fixture']['geometry']['pass_exterior'] and q['fixture']['pass_original_upper_headroom'] and
             q['legend']['pass_similarity'] and q['legend']['pass_modes'] and not q['clear_displacement'], 'unexpected R7 rejection')
        for v in VARS: stack[v][k//3].append(descriptor(a,v))
    seen=set()
    with (R7/'trace_ordinals/ordinal_pairs.csv').open() as f:
        for row in csv.DictReader(f):
            v=tuple(int(row[k]) for k in ('threshold','dx','dy'));i,j=(int(row[k][1:]) for k in ('a','b'))
            val=dvalues(stack[v],i,j)
            need(0<=i<=j<14 and (v,i,j) not in seen and int(row['n'])==len(val) and all(
                abs(s/38520-float(row[k]))<=0.500001e-6 for s,k in zip((min(val),median(val),max(val)),('Dmin','Dmed','Dmax'))),'ordinal replay')
            seen.add((v,i,j))
    need(len(seen)==735,'incomplete ordinal replay')
    return dict(variants={str(v):summary(stack[v],range(14)) for v in VARS},csv_rows=len(seen),
                rejected_glyph_ncc=failed,planned_slots=51,captured_slots=len(names),accepted_slots=42,missing_slots=8)


def sham(src):
    rows=read(src/'sham_validity_series.json');pub=read(SHAM/'outcome.json')['samples']
    need(len(rows)==len(pub)==51,'51 slots required')
    data={i:[] for i in range(17)};starts=[];passes=[]
    for i,(r,p) in enumerate(zip(rows,pub)):
        need(r['index']==p['index']==i and all(r[k]==p[k] for k in ('fixture','legends','shadows')), 'sham QC binding')
        a=rgb(src/f'S{i:02d}.png')
        original_checks(a,r['fixture'])
        passes.append(all([r['fixture']['geometry']['pass_exterior'],r['fixture']['pass_original_upper_headroom'],r['legends']['pass_similarity'],r['legends']['pass_modes']]))
        data[i//3].append(descriptor(a,VARS[0]))
        starts.append(datetime.fromisoformat(r['png_utc'][0]))
    need(all(a<b for a,b in zip(starts,starts[1:])) and all(passes),'sham ordering or acceptance')
    mid=starts[0]+(starts[-1]-starts[0])/2
    parts={'full':list(range(17)),'first':[i for i in range(17) if starts[3*i+2]<mid],
           'last':[i for i in range(17) if starts[3*i]>=mid]}
    out={k:dict(phases=phases,**summary(data,phases)) for k,phases in parts.items()}
    out.update(midpoint_s=round((mid-starts[0]).total_seconds(),6),
               straddles=sorted(set(range(17))-set(parts['first'])-set(parts['last'])),
               badge_pass_by_time=[sum(p for p,t in zip(passes,starts) if t<mid),sum(p for p,t in zip(passes,starts) if t>=mid)])
    return out


def run(r12,rseven,sh):
    code,shifts=codes(r12)
    return dict(R103=code,R104=r7(rseven),R105=shifts,R106=sham(sh))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('r12b','r7','sham'): p.add_argument(arg,type=Path)
    a=p.parse_args()
    print(json.dumps(run(a.r12b,a.r7,a.sham),indent=2,allow_nan=False))
