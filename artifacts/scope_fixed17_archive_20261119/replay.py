"""Offline replay of the R109 photograph feature; stdout contains only sanitized numbers."""
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image

REV = "76f3c5bb898eaa7e972ab6447872f88586a7cc44"
CASES = {
    "dc3600": ("dc", [("1_0",3600,0),("2_1",3600,1),("3_0",3600,0)]),
    "dc3601": ("dc3601", [("1_0",3601,0),("2_1",3601,1),("3_0",3601,0)]),
    "boundary": ("boundary", list(zip(["base","1_3600","2_3601","3_3602","4_3601","5_3600","restored"],[6879,3600,3601,3602,3601,3600,6879],[0]*7))),
    "color": ("color", [(s,3600,0) for s in ("1_white","2_black","3_white")]),
    "spatial": ("spatial", [(s,3600,0) for s in ("1A","2B","3A","4B","5A")]),
}

def need(condition, reason):
    if not condition:
        raise ValueError(reason)

def acf_peaks(s):
    corr = [np.corrcoef(s[:-k], s[k:])[0, 1] for k in range(5,125)]
    return [[i+5, round(float(v),4)] for i,v in enumerate(corr)
            if 0<i<len(corr)-1 and v>max(.25,corr[i-1],corr[i+1])]

def features(s):
    need(s.shape == (714,), "fixed width")
    a = 2*abs(np.dot(s, np.exp(-2j*np.pi*np.arange(714)/17)))/714
    need(abs(a - 2*abs(np.fft.rfft(s)[42])/714)<1e-9, "DFT consistency")
    z = 2/17*(s.reshape(42,17) @ np.exp(-2j*np.pi*np.arange(17)/17))
    b = float(np.mean(abs(z)))
    need(abs(a-abs(z.mean()))<1e-9, "period decomposition")
    return float(a), b, float(abs(z.mean())/b) if b>1e-9 else None

def replay(key, receipt):
    archive, phases = CASES[key]
    rows = json.loads(receipt.read_text())["phases"]
    need([r["phase"] for r in rows]==[p for p,_,_ in phases], "phase order")
    pub = subprocess.check_output(["git","show",f"{REV}:artifacts/scope_{archive}_divergence_20261118/native_qc.csv"],text=True)
    refs = list(csv.DictReader(io.StringIO(pub)))
    fingerprints = {(r["phase"],r["frame"]):r for r in refs}
    need(len(fingerprints)==len(refs)==len(phases)*3, "published roster")
    out = []
    for row,(name,dbv,dc) in zip(rows,phases):
        for side in ("start","end"):
            state = row[side]
            need((str(state["brightness"]),str(state["dc"]),state["provider"]) ==
                 (str(dbv),str(dc),"Result: Bundle[{value="+str(dc)+"}]"), "archival readback")
        need(len(row["frames"])==3, "three frames required")
        measures = []
        for stem,_ in row["frames"]:
            need(Path(stem).name==stem and (name,stem) in fingerprints, "frame not in published roster")
            fingerprint = fingerprints.pop((name,stem))
            with Image.open(receipt.parent/(stem+".png")) as im:
                need(im.size==(1080,2392), "native PNG dimensions")
                red = np.asarray(im.convert("RGB").getchannel("R"))
            trace = np.median(red[926:958,105:825],axis=0)
            grid = np.quantile(red[1072:1126,132:798],.8,axis=0)
            need(acf_peaks(trace)==json.loads(fingerprint["trace_lag_px_rho"])
                 and acf_peaks(grid)==json.loads(fingerprint["grid_lag_px_rho"]),
                 "historical trace/grid fingerprint disagreement")
            measures.append(features(trace[:714]))
        vectors = list(zip(*measures))
        med = lambda x: round(float(np.median(x)),6)
        out.append({"phase":name,"red_code_amplitude":[round(v,6) for v in vectors[0]],
                    "median_A17":med(vectors[0]),"diagnostic_median_local_magnitude":med(vectors[1]),
                    "diagnostic_median_coherence":med(vectors[2])})
    need(not fingerprints, "missing published frame")
    return out

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for case in CASES:
        parser.add_argument("--"+case,required=True,type=Path,metavar="RECEIPT")
    args=parser.parse_args()
    print(json.dumps({key:replay(key,getattr(args,key)) for key in CASES},indent=2))

if __name__=="__main__":
    main()
