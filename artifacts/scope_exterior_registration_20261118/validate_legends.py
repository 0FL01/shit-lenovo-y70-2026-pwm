"""Sanitized offline audit of the frozen legend checker including limited synthetic negatives."""
import argparse
import json
from pathlib import Path

import numpy as np

from exterior import load
from future import reference
from legends import ARROWS, GLYPHS, checks
from validate import EXPECTED


def audit(roots):
    ref=reference(roots[0]/"new_qual0.png")
    archive=[]; probes=[]
    for j,root in enumerate(roots):
        for n in sorted(EXPECTED[j]):
            q=checks(ref,load(root/(n+".png")))
            archive.append(dict(session=j+1,tag=n,ok=q["pass_similarity"],
                whole_min=min(x["ncc"] for x in q["glyphs"].values()),
                part_min=min(x["part_min"] for x in q["glyphs"].values()),
                color_max=max(x["color_delta"] for x in q["glyphs"].values()),
                marker_iou_min=min(x["iou"] for x in q["arrows"].values())))
    for key,(x,y,r,b,channel) in GLYPHS.items():
        for k in ("erase","erase_left_third","recolor"):
            a=ref.copy(); p=a[y:b,x:r]
            # Eliminate glyph structure without erasing the badge outside this window.
            if k=="erase":
                p[:]=np.median(p,axis=(0,1))
            elif k=="erase_left_third":
                p[:,:p.shape[1]//3]=np.median(p,axis=(0,1))
            else:
                # Rotate all RGB channels; swapping R/B only is ineffective for green.
                p[:]=p[:,:,[1,2,0]]
            q=checks(ref,a)
            probes.append(dict(kind=k,id=key,ok=q["pass_similarity"],details=q["glyphs"][key]))
    for key,(x,y,r,b) in ARROWS.items():
        for kind in ("remove","shift+4y","desaturate"):
            a=ref.copy(); p=a[y:b,x:r]
            if kind=="remove":
                p[:]=0
            elif kind=="shift+4y":
                p[4:]=p[:-4].copy(); p[:4]=0
            else:
                p[:]=np.median(p,axis=2)[:,:,None]
            q=checks(ref,a)
            probes.append(dict(kind=kind,id=key,ok=q["pass_similarity"],details=q["arrows"][key]))
    return dict(archive=archive,probes=probes)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("roots",type=Path,nargs=3)
    print(json.dumps(audit(p.parse_args().roots),indent=2,allow_nan=False))
