"""Frozen, independent color/glyph and arrow similarity veto. Not OCR or a channel identifier."""
from argparse import ArgumentParser
import json
from pathlib import Path
import numpy as np
from exterior import load
from future import reference

# Inner glyph patches only, no outlines of the badges. Fixed order and dominant channel.
GLYPHS = {
    "AUTO": (86, 937, 139, 959, 1), "10mV": (83, 1300, 139, 1321, 1),
    "X1": (193, 1300, 226, 1319, 1), "5mS": (292, 1297, 335, 1318, 2),
    "AC": (398, 1297, 435, 1318, 1), "RUN": (494, 1297, 540, 1317, 1)}
ARROWS = {"left": (45,1120,63,1140), "right": (557,1272,575,1290)}


def corr(a,b):
    a=a-a.mean(); b=b-b.mean()
    return float((a*b).sum()/max(1e-9, np.sqrt((a*a).sum()*(b*b).sum())))


def hp(p):
    # High-pass on the interior: ignore uniform fill and overall luminance.
    view=np.lib.stride_tricks.sliding_window_view(p,(5,5))
    return p[2:-2,2:-2]-view.mean(axis=(-2,-1))


def glyph(ref,im,box):
    x,y,r,b,c=box
    template=ref[y:b,x:r].astype(float)
    t=hp(template[:,:,c])
    rgb=np.median(template.reshape((-1,3)),axis=0)
    best=None
    for dy in range(-1,2):
        for dx in range(-1,2):
            p=im[y+dy:b+dy,x+dx:r+dx].astype(float)
            g=hp(p[:,:,c])
            whole=corr(t,g)
            if best is None or whole>best[0]:
                # Three adjacent slices: partial character changes are not necessarily
                # invisible just because the rest of the panel still matches.
                sub=min(corr(i,j) for i,j in zip(np.array_split(t,3,axis=1),np.array_split(g,3,axis=1)))
                color=np.median(p.reshape((-1,3)),axis=0)
                cd=float(abs(rgb/max(1,rgb.sum())-color/max(1,color.sum())).max())
                best=(whole,sub,cd,float(g.std()/max(1e-9,t.std())),dx,dy)
    n,sub,cd,ratio,dx,dy=best
    return dict(ok=n>=.80 and sub>=.65 and cd<=.12 and .60<=ratio<=1.65,
                ncc=n,part_min=sub,color_delta=cd,contrast_ratio=ratio,dx=dx,dy=dy)


def arrow(ref,im,box):
    x,y,r,b=box
    def mask(v):
        p=v[y:b,x:r].astype(float)
        rg=np.minimum(p[:,:,0],p[:,:,1])
        return (rg-p[:,:,2]>=20) & (rg>=30)
    a,z=mask(ref),mask(im)
    union=(a|z).sum()
    iou=float((a&z).sum()/max(1,union))
    area=float(z.sum()/max(1,a.sum()))
    shift=float(np.abs(np.array(np.where(a)).mean(axis=1)-np.array(np.where(z)).mean(axis=1)).max()) if z.any() and a.any() else None
    return dict(ok=bool(a.sum()>=20 and iou>=.65 and .7<=area<=1.4 and shift is not None and shift<=2),
                iou=iou,area_ratio=area,shift=shift)


def checks(ref,im):
    g={k:glyph(ref,im,box) for k,box in GLYPHS.items()}
    m={k:arrow(ref,im,box) for k,box in ARROWS.items()}
    return dict(pass_similarity=all(v["ok"] for v in [*g.values(),*m.values()]),
                glyphs=g,arrows=m)


if __name__=="__main__":
    p=ArgumentParser(description=__doc__)
    p.add_argument("template",type=Path)
    p.add_argument("frames",type=Path,nargs="+")
    a=p.parse_args(); ref=reference(a.template)
    out=[checks(ref,load(f)) for f in a.frames]
    print(json.dumps(out,allow_nan=False,indent=2))
    raise SystemExit(0 if all(z["pass_similarity"] for z in out) else 2)
