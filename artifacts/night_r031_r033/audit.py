"""R11 paired preview statistics and exact whitelist map; R7 readout guard. Offline only."""
from pathlib import Path
import argparse, csv, hashlib, json, sys
import numpy as np
from PIL import Image
D = Path(__file__).resolve().parent
sys.path.insert(0,str(D.parent/'stock_expert_direct_r11_20261118'/'visibility'))
from replay import geometry, NAMES
W,H=1080,2392
WITNESSES=((920,915,974,965),(988,918,1053,975))
def roles():
    _,_,_,mask,_=geometry()
    m=np.zeros((H,W),dtype='uint8')
    for role,x in [(1,900),(2,100)]:
        m[910:1335,x:x+180][mask]=role
    for x,y,X,Y in WITNESSES:
        if m[y:Y,x:X].any():raise ValueError('overlap')
        m[y:Y,x:X]=3
    if tuple((m==k).sum() for k in (1,2)) != (1280,1280):raise ValueError('support')
    return m
def stats(a,mask):
    z=a[mask]
    return dict(n=len(z),mean_y=float(z.mean(axis=0)@np.array([.2126,.7152,.0722])),
                any0=int((z==0).any(1).sum()),any255=int((z==255).any(1).sum()))
def relative(auto,short):
    t=auto['direct']['mean_y']/short['direct']['mean_y']
    b=auto['background']['mean_y']/short['background']['mean_y']
    return dict(direct=t,background=b,direct_over_background=t/b,within_10_percent=1/1.1<=t/b<=1.1)
def paired(root,m):
    frames={}; hashes=set()
    for n in NAMES:
        p=root/(n+'.png')
        h=hashlib.sha256(p.read_bytes()).digest()
        if h in hashes:raise ValueError('duplicate R11 frame')
        hashes.add(h)
        with Image.open(p) as im:
            if im.size!=(W,H) or im.format!='PNG':raise ValueError('bad input')
            a=np.asarray(im.convert('RGB'))
        frames[n]={name:stats(a,m==k) for k,name in [(1,'direct'),(2,'background')]}
    boxes={}
    for k,name in [(1,'direct'),(2,'background'),(3,'witnesses_union')]:
        y,x=np.nonzero(m==k);boxes[name]=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]
    return dict(frames=frames,box_exclusive=boxes,ratios={n:relative(frames[NAMES[0]],frames[n]) for n in NAMES[1:]})
def save_mask(m,path):
    # Index is role ID; no optical samples. Full-frame lossless geometry.
    im=Image.fromarray(m).convert('P')
    im.putpalette([24,24,24,250,165,30,60,180,245,157,94,205]+[0]*(768-12))
    im.save(path)
def verify_legends(root,reads=D/'legend_reads.csv'):
    # Manual labels belong to the original, not merely to another file with the same name.
    with reads.open() as f:rows=list(csv.DictReader(f))
    names=[f'P{i:02d}_s{j}' for i in range(17) for j in range(3)]
    if [r['slot'] for r in rows]!=names:raise ValueError('incomplete manifest')
    actual={p.stem for p in root.glob('P[0-9][0-9]_s[0-9].png')}
    expected={r['slot'] for r in rows if r['original_qc']!='missing'}
    if actual!=expected:raise ValueError('unexpected or missing input')
    groups={};unread=[];missing=[]
    for r in rows:
        n=r['slot']; flags=[r[k] for k in ('multiplier','time_label','coupling')]
        if n not in expected:
            if flags!=['','',''] or r['source_sha256']:raise ValueError('fabricated missing data')
            missing.append(n); continue
        if hashlib.sha256((root/(n+'.png')).read_bytes()).hexdigest()!=r['source_sha256']:raise ValueError('source mismatch '+n)
        if any(v in ('','unknown') for v in flags):unread.append(n);continue
        groups.setdefault(' / '.join(flags),[]).append(n)
    return dict(groups=groups,unreadable=unread,missing=missing)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('r11',type=Path);p.add_argument('r7',type=Path);p.add_argument('--mask',type=Path)
    a=p.parse_args();m=roles()
    if a.mask:save_mask(m,a.mask)
    print(json.dumps(dict(r11=paired(a.r11,m),r7=verify_legends(a.r7)),indent=2,allow_nan=False))
