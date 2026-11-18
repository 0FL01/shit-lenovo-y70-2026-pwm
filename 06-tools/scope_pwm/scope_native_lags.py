"""Native-size counterpart to the normalized-raster lag and grid checks."""
import argparse
import json
from pathlib import Path
from scope_bench_receipt import read_receipt
import numpy as np
from PIL import Image
from scope_divergence import write_csv

def peaks(y):
    corr=[np.corrcoef(y[:-k],y[k:])[0,1] for k in range(5,125)]
    return [(i+5,round(float(s),4)) for i,s in enumerate(corr)
            if 0<i<len(corr)-1 and s>max(.25,corr[i-1],corr[i+1])]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    j=read_receipt(args.receipt)
    result=[]
    for ph in j["phases"]:
        for stem,_ in ph["frames"]:
            if Path(stem).name!=stem:
                raise ValueError("not basename")
            with Image.open(args.receipt.parent/(stem+".png")) as im:
                if im.size!=(1080,2392):
                    raise ValueError("dimensions")
                red=np.asarray(im.convert("RGB").getchannel("R"))
            x=np.median(red[926:958,105:825],axis=0)
            grid=np.quantile(red[1072:1126,132:798],.8,axis=0)
            result.append([ph["phase"],stem,json.dumps(peaks(x)),json.dumps(peaks(grid))])
    write_csv(args.output,["phase","frame","trace_lag_px_rho","grid_lag_px_rho"],result)

if __name__=="__main__":
    main()
