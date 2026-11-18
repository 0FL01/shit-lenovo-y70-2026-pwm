"""Offline gate for a fixed 1080x2392 preview framing. No acquisition or hardware I/O."""
from argparse import ArgumentParser
import json
from pathlib import Path
import numpy as np
from PIL import Image


# name, (left, top, right, bottom), normal axis in RGB raster, nominal blue ridge
ANCHORS = (
    ("top-right/a", (493,952,513,981), "y", 963),
    ("top-right/b", (517,952,538,981), "y", 963),
    ("right-upper/a", (542,974,569,989), "x", 554),
    ("right-upper/b", (542,990,569,1005), "x", 554),
    ("top-left", (225,951,245,983), "y", 965),
    ("right-lower", (543,1258,570,1272), "x", 556),
    ("bottom-right", (470,1277,492,1298), "y", 1289),
)


def ridge(img, box, axis):
    l,t,r,b = box
    a = img[t:b,l:r].astype(float)
    # Scope graticule is blue, not the yellow trace. Median reduces isolated contamination.
    ex = a[:,:,2] - (a[:,:,0]+a[:,:,1])/2
    p = np.median(ex,axis=0 if axis=="x" else 1)
    k = int(np.argmax(p))
    bg = np.median(np.r_[p[:3],p[-3:]])
    height = float(p[k]-bg)
    half = np.flatnonzero(p > bg + height/2)
    # Entire occupied span, not just the connected component around the winning peak.
    width = int(half[-1]-half[0]+1) if half.size else 0
    # Adjacent contrast at the selected ridge, not a remote strongest change.
    lo,hi = max(0,k-2), min(len(p),k+3)
    gradient = float(np.abs(np.diff(p[lo:hi])).max())
    return dict(pos=k+(l if axis=="x" else t), height=height, grad=gradient, width=width)


def score(img, ref=None):
    if img.shape != (2392,1080,3) or img.dtype != np.uint8:
        raise ValueError("requires unmodified 1080x2392 RGB preview")
    anchors = {}
    reasons = []
    for name,box,axis,nom in ANCHORS:
        s = ridge(img,box,axis)
        anchors[name] = s
        if (abs(s["pos"]-nom)>2 or s["height"]<10 or s["grad"]<5
                or not 1<=s["width"]<=6):
            reasons.append(name+":absolute")
        if ref:
            v=ref[name]
            if (abs(s["pos"]-v["pos"])>2 or s["height"]<.65*v["height"]
                    or s["grad"]<.65*v["grad"] or s["width"]>v["width"]+2):
                reasons.append(name+":relative")
    for a,b in (("top-right/a","top-right/b"),("right-upper/a","right-upper/b")):
        if abs(anchors[a]["pos"]-anchors[b]["pos"])>1:
            reasons.append(a+":inconsistent")
    face=img[930:1340,80:575]
    tr=img[1080:1270,112:540]
    cap=int(face.max()),int(tr.max())
    if cap[0]>=255 or cap[1]>=250:
        reasons.append("highlights")
    return dict(pass_geometry_highlights=not reasons, failures=reasons,
                anchors=anchors, face_max=cap[0], trace_max=cap[1],
                trace_zero_rgb=[int(n) for n in (tr==0).sum(axis=(0,1))],
                trace_pixels=int(tr.shape[0]*tr.shape[1]))


def reference(images):
    images=list(images)
    if len(images)!=3:
        raise ValueError("requires exactly three commissioning frames")
    first=[score(a) for a in images]
    if any(not s["pass_geometry_highlights"] for s in first):
        raise ValueError("commissioning absolute gate")
    ref={name:{k:float(np.median([s["anchors"][name][k] for s in first]))
               for k in ("pos","height","grad","width")} for name, *_ in ANCHORS}
    if any(not score(a,ref)["pass_geometry_highlights"] for a in images):
        raise ValueError("unstable commissioning frames")
    return ref


def load(p):
    with Image.open(p) as im:
        if im.format!="PNG": raise ValueError("expected original preview PNG")
        return np.asarray(im.convert("RGB"))


def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--ref",nargs=3,required=True,type=Path)
    p.add_argument("test",nargs="+",type=Path)
    args=p.parse_args(); ref=reference(load(x) for x in args.ref)
    result=[score(load(path),ref) for path in args.test]
    # Keep even local paths and basenames out of stdout; caller supplies ordinal order.
    print(json.dumps(result,allow_nan=False,indent=2))
    return 0 if all(s["pass_geometry_highlights"] for s in result) else 2


if __name__=="__main__":
    raise SystemExit(main())
