"""Ordinal-only descriptive comparison of fixed preview rasters. Does not read state logs."""
import argparse
import csv
import itertools
import json
from pathlib import Path
import re
import numpy as np
from PIL import Image


VARIANTS=((18,0,0),(12,0,0),(24,0,0),(18,-3,0),(18,3,0),(18,0,-3),(18,0,3))


def yellow(a):
    a=a.astype(float)
    return (a[:,:,0]+a[:,:,1])/2-a[:,:,2]


def descriptor(a,t,dx,dy):
    if a.shape!=(2392,1080,3):
        raise ValueError("wrong framing")
    exc=yellow(a[1150+dy:1240+dy,112+dx:540+dx])
    p=(exc>t).mean(0)
    l=np.array([np.mean(np.abs(p-np.roll(p,k))) for k in range(1,86)])
    return np.sort(p), l, p


def corr_peaks(x):
    # Pearson correlation over actual overlap; no circular seam for this secondary check.
    scores=[]
    for k in range(5,141):
        a=x[k:]-np.mean(x[k:])
        b=x[:-k]-np.mean(x[:-k])
        den=np.linalg.norm(a)*np.linalg.norm(b)
        scores.append(float(np.dot(a,b)/den) if den>0 else float("nan"))
    return [(i+5,round(s,4)) for i,s in enumerate(scores[1:-1],start=1)
            if np.isfinite(s) and s>.25 and s>scores[i-1] and s>scores[i+1]]


def feature(a,p):
    center=(yellow(a[1118:1137,112:540])>18).mean(1)
    # If several candidate center rows tie, publish no single coordinate.
    best=np.flatnonzero(center==center.max())
    row=int(best[0]+1118) if len(best)==1 and center.max()>0 else None
    g=a[1269:1282,112:540].astype(float)
    grid=np.median(g[:,:,2]-(g[:,:,0]+g[:,:,1])/2,axis=0)
    return [round(float(p.mean()),6),row,round(float(center.max()),6),
            json.dumps(corr_peaks(p)),json.dumps(corr_peaks(grid))]


def write_csv(f,header,rows):
    with f.open("x",newline="") as out:
        w=csv.writer(out,lineterminator="\n");w.writerow(header);w.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src",type=Path)
    parser.add_argument("new_dir",type=Path)
    # Only a separately validated contiguous prefix of *complete* triplets.
    parser.add_argument("--complete-blocks",type=int,required=True)
    args=parser.parse_args()
    if not 1<=args.complete_blocks<=17: raise ValueError("invalid complete-block count")
    blocks={}; rows=[]
    for i in range(args.complete_blocks):
        name=f"P{i:02d}"; blocks[name]=[]
        for j in range(3):
            f=args.src/f"{name}_s{j}.png"
            with Image.open(f) as im:
                if im.format!='PNG': raise ValueError("expected original PNG")
                a=np.asarray(im.convert('RGB'))
            d=[descriptor(a,*v) for v in VARIANTS]
            blocks[name].append(d)
            rows.append([name,j,*feature(a,d[0][2])])
    phase_rows=[]
    for k,(q,dx,dy) in enumerate(VARIANTS):
        for a,b in itertools.combinations_with_replacement(blocks,2):
            pairs=(itertools.combinations(blocks[a],2) if a==b
                   else itertools.product(blocks[a],blocks[b]))
            vals=np.array([[np.mean(abs(x[k][m]-y[k][m])) for m in (0,1)] for x,y in pairs])
            phase_rows.append([q,dx,dy,a,b,len(vals),*[round(float(z),6) for z in np.quantile(vals,[0,.5,1],axis=0).T.ravel()]])
    args.new_dir.mkdir(exist_ok=False)
    write_csv(args.new_dir/"ordinal_frames.csv",
              ["block","index","yellow_fraction","center_argmax_y","center_max_fraction","trace_lag_peaks_px_r","grid_lag_peaks_px_r"],rows)
    write_csv(args.new_dir/"ordinal_pairs.csv",
              ["threshold","dx","dy","a","b","n","Dmin","Dmed","Dmax","Lmin","Lmed","Lmax"],phase_rows)


if __name__=="__main__":
    main()
