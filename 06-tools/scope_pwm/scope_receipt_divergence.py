"""Read only a completed capture receipt. Compare every phase with every other phase."""
import argparse
import csv
import itertools
import json
from pathlib import Path
from scope_bench_receipt import read_receipt

import numpy as np
from scope_divergence import crop_red, profiles, descriptor, distances, write_csv

VARS = [(.97,0,0),(.95,0,0),(.98,0,0),(.97,-4,0),(.97,4,0),(.97,0,-2),(.97,0,2)]


def repeat(red):
    y=np.median(red[159:177,25:425],axis=0)
    if np.std(y)==0:
        return None,None
    scores=[np.corrcoef(y[:-i],y[i:])[0,1] for i in range(45,69)]
    if not np.isfinite(scores).all():
        return None,None
    k=int(np.argmax(scores))
    return 45+k,round(float(scores[k]),4)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt",type=Path)
    p.add_argument("out",type=Path,help="new directory")
    args=p.parse_args()
    j=read_receipt(args.receipt)
    data={}
    frame_rows=[]
    for ph in j["phases"]:
        phase=ph["phase"]
        if phase in data:
            raise ValueError("duplicate phase")
        data[phase]=[]
        for stem,date in ph["frames"]:
            if Path(stem).name!=stem:
                raise ValueError("not basename")
            red=crop_red(args.receipt.parent/(stem+".png"))
            data[phase].append(red)
            t,s=profiles(red)
            frame_rows.append([phase,stem,date,t,*([*s.mean(axis=1),*repeat(red),"ok"] if s is not None
                            else ["","","","","unresolved-reference"])])
    args.out.mkdir(exist_ok=False)
    write_csv(args.out/"frames.csv",["phase","capture","utc","ref_threshold","upper_fraction",
            "lower_fraction","repeat_px_in_45_68","rho","status"],frame_rows)
    rows=[]
    for q,dx,dy in VARS:
        d={}
        for phase,arrs in data.items():
            prof=[profiles(r,q,dx,dy)[1] for r in arrs]
            d[phase]=[descriptor(s) for s in prof if s is not None]
        for a,b in itertools.combinations_with_replacement(d,2):
            pairs=itertools.combinations(d[a],2) if a==b else itertools.product(d[a],d[b])
            vals=np.array([distances(x,y) for x,y in pairs])
            if len(vals):
                rows.append([q,dx,dy,a,b,len(vals),*[round(float(x),6) for x in
                            np.quantile(vals,[0,.5,1],axis=0).T.ravel()]])
    write_csv(args.out/"pairs.csv",["ref_q","dx","dy","a","b","n","Dmin","Dmed","Dmax","Lmin","Lmed","Lmax"],rows)


if __name__=="__main__":
    main()
