"""Reanalyse all 51 unchanged-state PNGs; write only derived ordinal results."""
import argparse
import csv
import datetime as dt
import itertools
import json
from pathlib import Path
import tempfile

import numpy as np

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "stock_dbv_2632_20261118"
STEPS = [2632,2632,2633,2632,2631,2632,2633,2634,2633,2632,2633,2633,2634,2633,2632,2631,2632]

def stats(xs):
    return [round(float(x), 6) for x in np.quantile(xs, [0,.5,1])]

def summarize(rows, labels):
    within, adjacent, remote, all_between = [], [], [], []
    target, controls, up, down = [], [], [], []
    for row in rows:
        i,j = [int(row[k][1:]) for k in ("a","b")]
        d = float(row["Dmed"])
        a,b = labels[i],labels[j]
        if i == j:
            within.append(d)
        else:
            all_between.append(d)
        if j-i == 1:
            adjacent.append(d)
        if j-i >= 8:
            remote.append(d)
        if j-i == 1 and {a,b} == {2632,2633}:
            target.append(d)
            (up if a < b else down).append(d)
        elif a == b or (j-i == 1 and {a,b} in ({2631,2632},{2633,2634})):
            controls.append(d)
    return {"within": stats(within), "adjacent":stats(adjacent), "lag_ge8":stats(remote),
            "all_between":stats(all_between), "pseudo_up":stats(up), "pseudo_down": stats(down),
            "pseudo_control":stats(controls), "n_pseudo_target":len(target),"n_pseudo_ctrl":len(controls),
            "pseudo_margin":round(min(target)-max(controls),6)}

def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

def pipeline(src, out):
    series=json.loads((src/"sham_validity_series.json").read_text())
    if [s["index"] for s in series] != list(range(51)): raise ValueError("incomplete or reordered series")
    for s in series:
        if not all([s["fixture"]["geometry"]["pass_exterior"],s["fixture"]["pass_original_upper_headroom"],
                    s["legends"]["pass_modes"]]): raise ValueError("failed local QC")
    starts, ends = np.array([[dt.datetime.fromisoformat(x).timestamp() for x in s["png_utc"]] for s in series]).T
    if not (np.all(ends>=starts) and np.all(starts[1:]>ends[:-1])): raise ValueError("invalid time windows")
    # Reuse the actual frozen executable, not a reimplementation of its feature extraction.
    import subprocess, sys
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)
        for k in range(51):
            f=(src/f"S{k:02}.png").resolve(strict=True)
            (stage/f"P{k//3:02}_s{k%3}.png").symlink_to(f)
        subprocess.run([sys.executable,str(PRIOR/"analysis_ordinals.py"),str(stage),str(out),
                        "--complete-blocks","17"],check=True)
    rows=read_csv(out/"ordinal_pairs.csv")
    groups=itertools.groupby(rows,lambda r:(r["threshold"],r["dx"],r["dy"]))
    summary={",".join(k):summarize(list(g), STEPS) for k,g in groups}
    fr=read_csv(out/"ordinal_frames.csv")
    trace=[json.loads(r["trace_lag_peaks_px_r"]) for r in fr]
    grid=[json.loads(r["grid_lag_peaks_px_r"]) for r in fr]
    y=[float(r["yellow_fraction"]) for r in fr]
    centers=[int(r["center_argmax_y"]) for r in fr if r["center_argmax_y"]]
    common_lags=sorted(set.intersection(*[{k for k,_ in peaks} for peaks in trace]))
    out_data={"common_trace_lags_px":common_lags,"D":summary, "png_start_span_s":round(float(starts[-1]-starts[0]),6),
              "png_start_gap_s":stats(np.diff(starts)), "png_command_window_s":stats(ends-starts),
              "within_triplet_png_start_span_s":stats(starts[2::3]-starts[::3]),
              "yellow_fraction":stats(y), "block_median_yellow_fraction":[round(float(np.median(y[i:i+3])),6) for i in range(0,51,3)],
              "center_unique_n":len(centers), "center_unique_px":stats(centers) if centers else [],
              "trace_peak_frames":sum(bool(a) for a in trace), "grid_peak_frames":sum(bool(a) for a in grid),
              "both_peak_frames":sum(bool(a and b) for a,b in zip(trace,grid)),
              "trace_grid_peak_within2px_frames":sum(any(abs(x[0]-z[0])<=2 for x in a for z in b) for a,b in zip(trace,grid)),
              "blue_zero_fraction_large_trace_roi":stats([s["fixture"]["trace_zero_rgb"][2]/s["fixture"]["trace_pixels"] for s in series])}
    (out/"summary.json").write_text(json.dumps(out_data,indent=2)+"\n")

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_src",type=Path)
    p.add_argument("new_output",type=Path)
    a=p.parse_args()
    pipeline(a.private_src, a.new_output)
