"""Compare two trusted, separately acquired, scene-matched 0/1/0 DC receipts."""
import argparse
import hashlib
import itertools
from pathlib import Path
import sys

import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"06-tools"/"scope_pwm"))
from scope_bench_receipt import read_receipt
from scope_divergence import crop_red, descriptor, profiles, distances, write_csv
from scope_receipt_divergence import VARS

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("r3600",type=Path)
    p.add_argument("r3601",type=Path)
    p.add_argument("new_csv",type=Path)
    args=p.parse_args()
    scene=None
    data={}
    for dbv,path in ((3600,args.r3600),(3601,args.r3601)):
        j=read_receipt(path)
        if [s["phase"] for s in j["phases"]]!=["1_0","2_1","3_0"]:
            raise ValueError("expected 0/1/0 experiment")
        for i,ph in enumerate(j["phases"]):
            state=ph["start"]
            dc=(0,1,0)[i]
            if (state["brightness"]!=str(dbv) or state["dc"]!=str(dc)
                    or f"value={dc}" not in state["provider"] or "120.00 Hz" not in state["sf"]):
                raise ValueError("unexpected bench condition")
            with Image.open(path.parent/f"target-dc-{i+1}.png") as im:
                if im.size!=(1440,3168):
                    raise ValueError("unexpected target geometry")
                w,h=im.size
                center=im.crop((w//4,h//4,3*w//4,3*h//4))
                sha=hashlib.sha256(center.tobytes()).hexdigest()
            if scene is None:
                scene=sha
            if sha!=scene or sha!=j["target_center"][i] or sha!=j["scenehash"]:
                raise ValueError("unmatched scene")
            key=f"{dbv}:{dc}"
            data.setdefault(key,[]).extend(crop_red(path.parent/(stem+".png")) for stem,_ in ph["frames"])
    rows=[]
    for q,dx,dy in VARS:
        ds={}
        for key,rasters in data.items():
            ps=[profiles(red,q,dx,dy)[1] for red in rasters]
            if any(v is None for v in ps):
                raise ValueError("unresolved reference")
            ds[key]=[descriptor(v) for v in ps]
        for a,b in itertools.combinations_with_replacement(ds,2):
            pairs=itertools.combinations(ds[a],2) if a==b else itertools.product(ds[a],ds[b])
            val=np.array([distances(x,y) for x,y in pairs])
            qs=np.quantile(val,[0,.5,1],axis=0).T.ravel()
            rows.append([q,dx,dy,a,b,len(val),*[round(float(x),6) for x in qs]])
    write_csv(args.new_csv,["ref_q","dx","dy","dbv_dc_a","dbv_dc_b","n","Dmin","Dmed","Dmax","Lmin","Lmed","Lmax"],rows)

if __name__=="__main__":
    main()
