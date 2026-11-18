"""Exploratory photo checks only: align the neutral graticule and list lag peaks."""
import argparse
import itertools
import json
from pathlib import Path
from scope_bench_receipt import read_receipt
import numpy as np
from scope_divergence import crop_red, write_csv


def main():
    cmd=argparse.ArgumentParser(description=__doc__)
    cmd.add_argument("receipt",type=Path)
    cmd.add_argument("output_csv",type=Path)
    a=cmd.parse_args()
    j=read_receipt(a.receipt)
    data=[]
    ref=None
    for ph in j["phases"]:
        for stem,_ in ph["frames"]:
            if Path(stem).name!=stem:
                raise ValueError("basename")
            red=crop_red(a.receipt.parent/(stem+".png"))
            if ref is None:
                ref=red[240:270,40:410].flatten()
            corr,x,y=max((np.corrcoef(ref,red[240+y:270+y,40+x:410+x].flatten())[0,1],x,y)
                         for x,y in itertools.product(range(-3,4),repeat=2))
            series=np.median(red[159:177,25:425],axis=0)
            rho=[np.corrcoef(series[:-k],series[k:])[0,1] for k in range(3,69)]
            peaks=[(i+3,round(float(s),4)) for i,s in enumerate(rho)
               if 0<i<len(rho)-1 and s>max(.25,rho[i-1],rho[i+1])]
            data.append([ph["phase"],stem,x,y,round(float(corr),5),json.dumps(peaks)])
    write_csv(a.output_csv,["phase","frame","grid_dx","grid_dy","grid_rho","lag_peaks_px_rho"],data)


if __name__=="__main__":
    main()
