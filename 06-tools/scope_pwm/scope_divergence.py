"""Host-only comparison of the 30 registered 5 ms/div scope photographs; no device I/O."""
import argparse
import csv
import hashlib
import itertools
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parents[2] / "artifacts/scope_calibration_20261118"
PAIRS = [("w1","w2"),("w2","w3"),("w1","blk"),("blk","w2"),("w2","hi"),
         ("hi","w3"),("w3","lockwhite"),("before","off"),("off","restored"),("before","restored")]


def crop_red(path):
    with Image.open(path) as im:
        if im.size != (1080,2392):
            raise ValueError(f"unexpected dimensions: {im.size}")
        return np.asarray(im.convert("RGB").crop((60,640,870,1280)).resize(
            (450,356), Image.Resampling.BICUBIC))[:,:,0]


def profiles(red, q=.97, dx=0, dy=0):
    # Integer order statistic, not interpolated: invariant to strictly monotone
    # per-frame remapping of the normalized red raster (not to clipping or local AE).
    col = slice(25+dx,425+dx)
    ref = red[244+dy:277+dy,col]
    t = float(np.quantile(ref, q, method="inverted_cdf"))
    if t >= 254 or t <= float(np.median(ref)):
        return t, None
    p = np.stack([(red[y+dy:y+dy+18,col] > t).mean(axis=0)
                  for y in (159,195)])
    return t, p


def descriptor(p):
    # Each row of the first term is the empirical quantile function of the
    # 400 column occupancies. The second term retains some horizontal structure.
    sorted_p = np.sort(p,axis=1)
    lag = np.stack([np.abs(p - np.roll(p,k,axis=1)).mean(axis=1)
                    for k in range(1,86)],axis=1)
    return sorted_p, lag


def distances(a,b):
    return tuple(float(np.abs(x-y).mean()) for x,y in zip(a,b))


def report(red_arrays, q, dx, dy):
    by_phase = defaultdict(list)
    frames = []
    for phase, name, red in red_arrays:
        t, p = profiles(red, q, dx, dy)
        frames.append([phase,name,t,*([*p.mean(axis=1),"ok"] if p is not None
                                       else ["","","unresolved-reference"])])
        if p is not None:
            by_phase[phase].append(descriptor(p))
    rows = []
    for a,b in [(k,k) for k in by_phase]+PAIRS:
        pairs = (itertools.combinations(by_phase[a],2) if a==b else
                 itertools.product(by_phase[a],by_phase[b]))
        ds = np.array([distances(x,y) for x,y in pairs])
        if len(ds):
            agg = [round(float(v),6) for v in np.quantile(ds,[0,.5,1],axis=0).T.ravel()]
            rows.append([q,dx,dy,a,b,len(ds),*agg])
    return frames,rows


def write_csv(path, header, rows):
    with path.open("x",newline="") as f:
        writer=csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("originals",type=Path)
    parser.add_argument("output",type=Path,help="new directory, never overwritten")
    args=parser.parse_args()
    frames=[]
    seen=set()
    for manifest in ("frames.csv","sleep_frames.csv"):
        with (HERE/manifest).open() as f:
            for row in csv.DictReader(f):
                name=row["original_basename"]
                if name != Path(name).name or name in seen:
                    raise ValueError("manifest basename")
                seen.add(name)
                path=args.originals/name
                if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:
                    raise ValueError(f"manifest hash mismatch for {name}")
                frames.append((row["phase"],name,crop_red(path)))
    if len(frames)!=30:
        raise ValueError("expected 30 manifest originals")
    args.output.mkdir(parents=False, exist_ok=False)
    primary, rows = report(frames,.97,0,0)
    write_csv(args.output/"frames.csv", ["phase","original","red_threshold",
              "upper_fraction","lower_fraction","status"],primary)
    hdr=["q","dx","dy","a","b","pairs","D_min","D_median","D_max",
         "L_min","L_median","L_max"]
    write_csv(args.output/"pairs.csv",hdr,rows)
    # One-factor-at-a-time perturbations; not confidence intervals.
    sensitivity = []
    for q,dx,dy in [(.95,0,0),(.98,0,0),(.97,-4,0),(.97,4,0),(.97,0,-2),(.97,0,2)]:
        _, rows = report(frames,q,dx,dy)
        sensitivity.extend(rows)
    write_csv(args.output/"sensitivity.csv",hdr,sensitivity)


if __name__=="__main__":
    main()
