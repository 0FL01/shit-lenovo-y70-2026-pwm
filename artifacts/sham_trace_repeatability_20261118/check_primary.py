"""Independent integer-count recomputation of all 153 default block-pair D values."""
import argparse
import csv
import itertools
from pathlib import Path
import numpy as np
from PIL import Image

def check(src, pairs):
    counts=[]
    for i in range(51):
        with Image.open(src/f"S{i:02d}.png") as im:
            if im.format != "PNG" or im.size != (1080,2392):
                raise ValueError(f"bad input format/dimensions at S{i:02d}")
            a=np.array(im.convert("RGB").crop((112,1150,540,1240)),dtype=np.int32)
        counts.append(sorted(((a[:,:,0]+a[:,:,1]-2*a[:,:,2])>36).sum(axis=0)))
    counts=np.asarray(counts)
    # Histogram/quantile-matched L1 is exact in integer column counts until division.
    raw=np.abs(counts[:,None,:]-counts[None,:,:]).sum(axis=-1)/(90*428)
    remaining=set(itertools.combinations_with_replacement([f"P{i:02d}" for i in range(17)],2))
    with pairs.open() as f:
        for row in csv.DictReader(f):
            if (row["threshold"],row["dx"],row["dy"])!=("18","0","0"): continue
            pair=(row["a"],row["b"])
            if pair not in remaining:
                raise ValueError(f"duplicate or unexpected block pair {pair}")
            remaining.remove(pair)
            a,b=[3*int(label[1:]) for label in pair]
            aa,bb=range(a,a+3),range(b,b+3)
            ix=itertools.combinations(aa,2) if a==b else itertools.product(aa,bb)
            x=[raw[i,j] for i,j in ix]
            if len(x)!=int(row["n"]):
                raise ValueError(f"wrong sample count for {pair}")
            if not np.allclose(np.quantile(x,[0,.5,1]),[float(row[k]) for k in ("Dmin","Dmed","Dmax")],atol=0.50001e-6,rtol=0):
                raise ValueError(f"quantile mismatch for {pair}")
    if remaining:
        raise ValueError(f"missing {len(remaining)} primary block pairs")
    print("153/153 primary block-pair min/median/max match at output precision")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("src",type=Path)
    p.add_argument("pairs",type=Path)
    a=p.parse_args()
    check(a.src,a.pairs)
