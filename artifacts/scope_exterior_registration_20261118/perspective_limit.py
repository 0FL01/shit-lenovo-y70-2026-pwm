"""Post-freeze adversarial limit: projective warp anchored along bottom row and AUTO."""
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image

from exterior import score
from future import reference


def demo(im):
    h=np.eye(3) + 4e-5*np.outer(np.array([140.,938.,1.]),np.array([0.,1.,-1316.]))
    inv=np.linalg.inv(h)
    coeff=(inv/inv[2,2]).ravel()[:8]
    out=np.asarray(Image.fromarray(im).transform((1080,2392),Image.Transform.PERSPECTIVE,
            coeff,resample=Image.Resampling.BILINEAR))
    corner=np.array([554.,963.,1.])
    q=h@corner
    result=score(im,out)
    return dict(corner_xy=corner[:2].tolist(),corner_shift=(q[:2]/q[2]-corner[:2]).tolist(),
          pass_exterior=result["pass_exterior"],patches=result["patches"])


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("template",type=Path)
    a=cli.parse_args()
    print(json.dumps(demo(reference(a.template)), indent=2,allow_nan=False))
