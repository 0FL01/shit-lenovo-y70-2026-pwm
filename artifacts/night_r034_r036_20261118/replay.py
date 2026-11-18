"""Offline replay. No device I/O; raw input is never copied or written."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "06-tools/scope_pwm"))
from scope_pwm import Calibration, Unresolved, measure

PAIRS = [(1, 11), (2, 10), (3, 9)]
HELD = [4, 5, 7, 8]
WINDOWS = [(145, 155), (248, 256), (352, 360), (453, 461),
           (556, 564), (658, 666), (760, 768)]


def grid(red):
    profile = np.quantile(red[1072:1126], .8, axis=0)
    marks = {}
    for k in sorted(set(sum((list(p) for p in PAIRS), []) + HELD)):
        left = 103 + 61 * k - 12
        v = profile[left:left + 25]
        peak = v.max()
        top = np.flatnonzero(v >= peak - 5)
        if (peak - np.median([v[0], v[-1]]) < 30 or top[0] == 0 or
                top[-1] == 24 or np.max(np.diff(top), initial=0) > 1):
            raise ValueError(f"unresolved grid mark {k}")
        marks[k] = left + float(top[0] + top[-1]) / 2
    fits = []
    for a, b in PAIRS:
        slope = (marks[b] - marks[a]) / (b - a)
        residual = [round(marks[k] - (marks[a] + (k-a)*slope), 4) for k in HELD]
        fits.append(dict(pair=[a,b], px_per_div=round(slope, 6),
                         residual_px_at_4_5_7_8=residual))
    return dict(marks=marks, fits=fits, passed=all(
        abs(r) <= 3 for f in fits for r in f["residual_px_at_4_5_7_8"]))


def edges(red, fits):
    p = np.median(red[926:958], axis=0)
    marks = []
    for a, b in WINDOWS:
        loc = []
        for threshold in [110,225]:
            cand = np.flatnonzero((p[a:b] < threshold) & (p[a+1:b+1] >= threshold))
            if not len(cand):
                raise ValueError("no threshold crossing")
            loc.append(a + int(cand[0]))
        if loc[0] > loc[1]:
            raise ValueError("threshold order")
        marks.append([loc[0], loc[1]+1])
    slopes = [f["px_per_div"] for f in fits]
    rows = []
    for n in [1,3,6]:
        lo, hi = marks[n][0] - marks[0][1], marks[n][1] - marks[0][0]
        # 5 ms per division is nominal, not a calibration certificate.
        t = [lo*5/max(slopes), hi*5/min(slopes)]
        rows.append(dict(n=n, span_px=[lo, hi],
                         span_ms=[round(v, 5) for v in t],
                         mean_ms=[round(v/n, 5) for v in t]))
    return dict(mark_intervals_px=marks, slopes_px_per_div=slopes, estimates=rows)


def synthetic():
    width, height, rgb = 380, 101, (230, 190, 40)
    x = np.arange(width)
    def run(y):
        im = Image.new("RGB", (width, height))
        ImageDraw.Draw(im).line(list(zip(x.tolist(), np.rint(y).astype(int).tolist())), fill=rgb)
        return measure(im, (0,0,width,height), rgb, 0, Calibration(.005,61,.01,30))
    counts = []
    for sigma in [2,8,18]:
        for amplitude in [1,3,6]:
            reasons, resolved = Counter(), []
            for seed in range(16):
                rng = np.random.default_rng(seed)
                centre = int(rng.integers(75, 305))
                noise = rng.integers(-amplitude, amplitude+1, width)
                y = 75 - 40*np.exp(-.5*((x-centre)/sigma)**2) + noise
                try:
                    r = run(y)
                    resolved.append([seed, r["period_px"], r["frequency_hz"]])
                except Unresolved as exc:
                    reasons[str(exc)] += 1
            counts.append(dict(sigma=sigma, amplitude=amplitude, unresolved=sum(reasons.values()),
                               reasons=dict(reasons), resolved=resolved))
    pos = run(np.where(x%40 < 12, 35, 75))
    return dict(negative=counts, positive_px=pos["period_px"],
                passed=all(row["unresolved"]==16 for row in counts) and abs(pos["period_px"]-40)<=1)


def replay(archive):
    with (ROOT / "artifacts/scope_calibration_20261118/frames.csv").open() as f:
        rows = list(csv.DictReader(f))
    audit, edge = [], None
    for i, row in enumerate(rows):
        name = row["original_basename"]
        if i != 0 and not name.endswith(("-2.png", "-3.png")):
            continue
        p = archive/name
        if hashlib.sha256(p.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("source identity mismatch: " + name)
        with Image.open(p) as im:
            if im.size != (1080,2392):
                raise ValueError("unexpected size")
            red = np.asarray(im.convert("RGB").getchannel("R"))
        try:
            g = grid(red)
        except ValueError as exc:
            if i == 0:
                raise
            g = dict(passed=False, reason=str(exc))
        if i == 0:
            edge = dict(frame=name, **edges(red,g["fits"]))
        else:
            audit.append(dict(frame=name, **g))
    if len(audit) != 12 or edge is None:
        raise ValueError("incomplete panel of source frames")
    return dict(R034=audit, R035=edge, R036=synthetic())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(json.dumps(replay(parser.parse_args().archive), indent=2, allow_nan=False))
