"""Audit these five trusted target bitmaps; aggregate pre-existing lag checks per block.

Outputs a new CSV; inputs stay private. The lag score is descriptive, not a
fundamental-frequency estimator or a measurement of modulation amplitude.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"06-tools"/"scope_pwm"))
from scope_bench_receipt import read_receipt


def score(x):
    # Always include all three lags, even when no local peak exceeds a threshold.
    vals=[np.corrcoef(x[:-lag],x[lag:])[0,1] for lag in (17,34,51)]
    if not np.isfinite(vals).all():
        raise ValueError("unresolved lag score")
    return float(np.mean(vals))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt",type=Path)
    p.add_argument("new_csv",type=Path)
    args=p.parse_args()
    j=read_receipt(args.receipt)
    phases=j["phases"]
    if [ph["phase"] for ph in phases]!=["1A","2B","3A","4B","5A"]:
        raise ValueError("expected ABABA bench")
    src=args.receipt.parent
    rows=[]
    bright=(np.arange(1440)>=360)&(np.arange(1440)<1080)
    for ph in phases:
        phase=ph["phase"]
        expected=255*(bright if phase[-1]=="A" else ~bright)
        with Image.open(src/("target-"+phase+".png")) as im:
            if im.size!=(1440,3168):
                raise ValueError("target dimensions")
            a=np.array(im.convert("RGB"))
        mismatch=int(np.any(a[400:3000]!=expected[None,:,None],axis=2).sum())
        if mismatch:
            raise ValueError("target screenshot differs from prescribed region")
        scores=[]
        for stem,_ in ph["frames"]:
            with Image.open(src/(stem+".png")) as im:
                if im.size!=(1080,2392):
                    raise ValueError("scope photograph dimensions")
                red=np.asarray(im.convert("RGB").getchannel("R"))
            scores.append(score(np.median(red[926:958,105:825],axis=0)))
        rows.append([phase,mismatch,round(float(a.mean()),6),*[round(s,6) for s in scores],
                     round(float(np.median(scores)),6)])
    with args.new_csv.open("x",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["phase","core_mismatched_px","whole_rgb_mean",
                         "lag_score_1","lag_score_2","lag_score_3","block_median"])
        writer.writerows(rows)

if __name__=="__main__":
    main()
