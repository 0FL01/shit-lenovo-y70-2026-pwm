"""Post-B extension; fixed odd corners in both return frames, without refit."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from replay import BASE, code, corners, locate

QUAD = ((2, 1), (6, 1), (2, 7), (6, 7))


def measure(marks):
    if len(marks) != 4 or [tuple(m['src']) for m in marks] != list(QUAD):
        raise ValueError('incorrect control rectangle')
    if not all(m['accepted'] for m in marks):
        return {'complete': False}
    tl, tr, bl, br = [np.asarray(m['xy']) for m in marks]
    top = tr-tl
    bottom = br-bl
    lens = np.linalg.norm([top, bottom], axis=1)
    return dict(complete=True, pitches_px=(lens/4).tolist(),
                relative_change=float(lens[1]/lens[0]-1),
                anchored_copy_error_px=float(np.linalg.norm(top-bottom)))


def run(raw):
    patterns = {(x,y):z for x,y,z in corners(code('A'),1)}
    hashes = json.loads((BASE/'private_evidence_hashes.json').read_text())
    result = {}
    for n in ('A20','A21'):
        p = raw/f'{n}.png'
        if hashlib.sha256(p.read_bytes()).hexdigest() != hashes[p.name]:
            raise ValueError('incorrect archive return image')
        with Image.open(p) as img:
            if img.size != (1080,2392):
                raise ValueError('preview dimensions')
            im = np.asarray(img.convert('RGB'),float) @ [.2126,.7152,.0722]
        marks = [locate(im,x,y,patterns[(x,y)]) for x,y in QUAD]
        result[n] = dict(landmarks=marks, **measure(marks))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('private_r10', type=Path)
    print(json.dumps(run(p.parse_args().private_r10), indent=2, allow_nan=False))
