"""Replay private fixed-framing captures; output only sanitized numeric summaries."""
from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from exterior import BOX, load, score

from future import reference

QUAL = ["new_qual0", "new_qual1", "new_qual2"]
EXPECTED = [QUAL + ["P00_s0"],
            QUAL + ["P00_s0", "P00_s1", "P00_s2", "P01_s0", "P01_s1"],
            QUAL + ["R00", "R01", "R02"]]


def row(ref, im):
    result = score(ref, im)
    p = result["patches"]
    return dict(ok=result["pass_exterior"], failures={key:v["failures"] for key,v in p.items()
                    if v["failures"]}, ncc_min=min(v["ncc"] for v in p.values()),
                pos_max=max(max(abs(v["dx"]), abs(v["dy"])) for v in p.values()),
                contrast_min=min(v["contrast"] for v in p.values()),
                sharp_min=min(v["sharp_ratio"] for v in p.values()),
                residual_max=max(v["mad"] for v in p.values()),
                peak_max=max(v["cap"] for v in p.values()),
                zero_max=max(v["zero_scalar_fraction"] for v in p.values()),
                trace_peak=int(im[1080:1270,112:540].max()),
                face_peak=int(im[930:1340,80:575].max()),
                trace_zero_fraction=float(np.mean(im[1080:1270,112:540]==0)))


def perturb(im, kind, dx=0, dy=0):
    if kind == "shift":
        return np.asarray(Image.fromarray(im).transform((im.shape[1],im.shape[0]),
               Image.Transform.AFFINE,(1,0,-dx,0,1,-dy),resample=Image.Resampling.BILINEAR))
    if kind == "blur":
        return np.asarray(Image.fromarray(im).filter(ImageFilter.GaussianBlur(3)))
    out = im.copy()
    if kind == "weak":
        out //= 4
    elif kind == "trace":
        rng = np.random.default_rng(0)
        out[963:1292,70:558] = rng.integers(256, size=out[963:1292,70:558].shape,dtype=np.uint8)
    elif kind == "occlude":
        x,y,r,b = BOX["time"]
        out[y:b,x:r] = 0
    elif kind == "clip":
        x,y,r,b = BOX["run"]
        out[y:b,x:r] = np.minimum(out[y:b,x:r].astype(int)*3, 255)
    else:
        raise ValueError(kind)
    return out


def validate(roots):
    ref = reference(roots[0]/"new_qual0.png")
    captures = []
    challenges = []
    for j, root in enumerate(roots):
        names = sorted({*root.glob("new_qual[0-9].png"),*root.glob("P[0-9][0-9]_s[0-9].png"),
                        *root.glob("R[0-9][0-9].png")})
        if sorted(p.stem for p in names) != sorted(EXPECTED[j]):
            raise ValueError("private archive inventory mismatch")
        for n in names:
            im = load(n)
            captures.append(dict(session=j+1, tag=n.stem, **row(ref,im)))
        base = load(root / "new_qual0.png")
        # Predictions on injected shifts are calibrated against each original itself,
        # avoiding the unknown pre-existing displacement in held-out files.
        for v in (-4.,-1.,.5,1.,4.):
            for axis in (0,1):
                shift = [0.,0.]
                shift[axis]=v
                s = score(base, perturb(base, "shift", *shift))
                err = max(max(abs(p["dx"]-shift[0]), abs(p["dy"]-shift[1]))
                          for p in s["patches"].values())
                challenges.append(dict(session=j+1, kind="shift", xy=shift,
                     observed=s["pass_exterior"], expected=abs(v)<=1., err_max=err))
        for kind in ("blur","weak","occlude","clip","trace"):
            s=score(base, perturb(base,kind))
            challenges.append(dict(session=j+1,kind=kind, expected=kind=="trace",
                        observed=s["pass_exterior"],
                        unchanged=s==score(base,base)))
    return dict(reference_sha256=hashlib.sha256((roots[0]/"new_qual0.png").read_bytes()).hexdigest(),
                captures=captures,challenges=challenges)


if __name__ == "__main__":
    cli=ArgumentParser(description=__doc__)
    cli.add_argument("roots", type=Path, nargs=3, metavar=("BOUNDARY","PROSPECTIVE","SHAM"))
    a=cli.parse_args()
    print(json.dumps(validate(a.roots),allow_nan=False,indent=2))
