"""Offline QC for this fixed framing only. Input PNGs stay private. No device I/O."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

# x0,y0,x1,y1; even the entire +/-6 search is outside the plotted graticule
# (approx y=963..1291). Never include the Open Camera overlay at x=67.
BOX = {"auto": (83, 920, 193, 956), "scale": (81, 1299, 157, 1337),
       "time": (270, 1299, 364, 1337), "run": (473, 1299, 563, 1337)}
R = 6


def load(path):
    with Image.open(path) as f:
        if f.format != "PNG" or f.size != (1080, 2392) or f.mode not in ("RGB", "RGBA"):
            raise ValueError("requires original fixed-size preview PNG")
        return np.asarray(f.convert("RGB"))


def scalar(im):
    if im.shape != (2392, 1080, 3) or im.dtype != np.uint8:
        raise ValueError("requires original fixed-size RGB raster")
    return im.max(axis=2)   # yellow, blue and green legends must all retain contrast


def features(p):
    c = np.percentile(p, 90) - np.percentile(p, 10)
    sharp = [float(np.percentile(abs(np.diff(p, axis=k)), 95) / max(c, 1))
             for k in (0, 1)]
    return float(c), np.array(sharp)


def parabolic(a, b, c):
    curvature = 2*b-a-c
    return float(np.clip((c-a)/(2*curvature), -.5, .5)) if curvature > 0 else 0.


def measure(t, search):
    t = t.astype(float)
    s = search.astype(float)
    h, w = t.shape
    v = t - t.mean()
    corr = np.full((2*R+1, 2*R+1), -1.)
    for y, x in np.ndindex(corr.shape):
        p = s[y:y+h, x:x+w]
        u = p - p.mean()
        n = np.sqrt((u*u).sum() * (v*v).sum())
        if n > 0:
            corr[y, x] = (u*v).sum()/n
    y, x = np.unravel_index(corr.argmax(), corr.shape)
    subx = parabolic(*corr[y, x-1:x+2]) if 0 < x < 2*R else 0.
    suby = parabolic(*corr[y-1:y+2, x]) if 0 < y < 2*R else 0.
    p = s[y:y+h, x:x+w]
    tc, ts = features(t)
    c, sharp = features(p)
    # Robust diagnostic of frame-to-template residual after brightness correction.
    # It includes raster refresh/ISP differences, and is not a sensor noise estimate.
    a = ((p-p.mean())*v).sum()/max(1., (v*v).sum())
    residual = p - a*t - (p-a*t).mean()
    mad = float(1.4826*np.median(abs(residual-np.median(residual))))
    reasons = []
    def need(good, name):
        if not good:
            reasons.append(name)
    need(tc >= 48 and min(ts) >= .10 and t.max() < 250, "bad_template")
    need(max(abs(x-R+subx), abs(y-R+suby)) <= 2., "position")
    need(corr[y, x] >= .92, "ncc")
    need(c >= 48 and .65*tc <= c <= 1.5*tc, "contrast")
    need(np.all(sharp >= .65*ts), "blur")
    need(p.max() < 250, "channel_headroom")
    need(mad <= c/8, "residual")
    return dict(dx=x-R+subx, dy=y-R+suby, ncc=float(corr[y,x]), contrast=c,
                sharp_ratio=float(min(sharp/np.maximum(ts,1e-9))), mad=mad,
                cap=int(p.max()), zero_scalar_fraction=float((p == 0).mean()), failures=reasons)


def score(template, frame):
    g, s = scalar(template), scalar(frame)
    out = {key: measure(g[y:b, x:r], s[y-R:b+R, x-R:r+R])
           for key, (x,y,r,b) in BOX.items()}
    return dict(pass_exterior=all(not a["failures"] for a in out.values()), patches=out)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("template", type=Path)
    cli.add_argument("frames", nargs="+", type=Path)
    args = cli.parse_args()
    ref = load(args.template)
    results = [score(ref, load(path)) for path in args.frames]
    print(json.dumps(results, allow_nan=False, indent=2))
    raise SystemExit(0 if all(r["pass_exterior"] for r in results) else 2)
