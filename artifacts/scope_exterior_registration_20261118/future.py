"""Offline prospective scoring only, not authority to start or admit a physical run."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from exterior import load, score

TEMPLATE_SHA256="98380bb50a422637c8248a83fb92b18c5f16951c1bd1215feba2e20c94d05d8a"


def reference(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("wrong fixed-framing reference: never substitute a frame")
    with Image.open(io.BytesIO(data)) as im:
        return np.asarray(im.convert("RGB"))


def checks(ref, im):
    geometry = score(ref, im)
    tr = im[1080:1270,112:540]
    face = int(im[930:1340,80:575].max())
    peak = int(tr.max())
    return dict(geometry=geometry, pass_original_upper_headroom=face<255 and peak<250,
                face_max=face, trace_max=peak, trace_zero_rgb=(tr==0).sum(axis=(0,1)).tolist(),
                trace_pixels=int(tr.shape[0]*tr.shape[1]))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("template",type=Path)
    p.add_argument("frames",type=Path,nargs="+")
    a=p.parse_args()
    r=reference(a.template)
    out=[checks(r,load(f)) for f in a.frames]
    print(json.dumps(out,allow_nan=False,indent=2))
    raise SystemExit(0 if all(z["geometry"]["pass_exterior"] and z["pass_original_upper_headroom"]
                              for z in out) else 2)
