"""Retrospective spatial calibration in the R10 preview. Reads local archive only."""
import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent / 'stock_direct_image_r10_20261118'
ANA = BASE / 'analysis'
SEEDS = {'A': 103820241, 'B': 937015809}
BASIS = np.array([[12., -1.], [1., 12.]])
ORIGIN = np.array([918., 1081.])


def code(name):
    rng = random.Random(SEEDS[name])
    out = np.zeros((8, 8), dtype=int)
    for row in out:
        row[rng.sample(range(8), 4)] = 1
    return out


def rank(obs, ref):
    choices = []
    for reflected in (0, 1):
        for k in range(4):
            t = np.rot90(np.fliplr(ref) if reflected else ref, k)
            for y in range(8):
                for x in range(8):
                    score = int(np.sum(obs == np.roll(t, (y, x), axis=(0, 1))))
                    choices.append((score, reflected, k, y, x))
    ordered = sorted(choices, reverse=True)
    best = ordered[0][0]
    return dict(correct=best, ties=sum(s[0] == best for s in ordered),
                runner_up=ordered[1][0], identity_wins=(best, 0, 0, 0, 0) in ordered)


def r025():
    result = json.loads((ANA / 'results.json').read_text())['phases']
    thresholds = np.array(json.loads((ANA / 'locked_transform.json').read_text())['thresholds'])[:, None]
    ans = {}
    for phase, rec in result.items():
        ref = code(phase[0])
        if phase.endswith('i'):
            ref = 1 - ref
        for frame, slot in enumerate(rec['frames']):
            observed = np.array(slot['cell_values']) >= thresholds
            ans[f'{phase}{frame}'] = rank(observed, ref)
    control = np.indices((8, 8)).sum(0) % 2
    return dict(archive=ans, checker=rank(control, control), flat=rank(control*0, control*0))


def corners(pattern, parity):
    for y in range(1, 8):
        for x in range(1, 8):
            z = pattern[y-1:y+1, x-1:x+1]
            if (y+x) % 2 == parity and (z[0, :] != z[1, :]).any() and (z[:, 0] != z[:, 1]).any():
                yield x, y, z


def locate(im, x, y, z):
    # Prior pose sets window, not the fitted or measured displacement.
    center = ORIGIN + BASIS @ [x, y]
    off = np.arange(-5, 6)
    gy, gx = np.meshgrid(off, off, indexing='ij')
    actual = im[(gy+int(center[1])).ravel(), (gx+int(center[0])).ravel()]
    actual = actual - actual.mean()
    shift = np.arange(-5., 5.01, .25)
    dy, dx = np.meshgrid(shift, shift, indexing='ij')
    offsets = np.stack((gx.ravel()-dx.ravel()[:, None], gy.ravel()-dy.ravel()[:, None]), axis=-1)
    t = offsets @ np.linalg.inv(BASIS).T
    # Fixed soft transitions, in nominal tile units. No image-dependent blur.
    sx, sy = np.moveaxis((np.tanh(t/.08)+1)/2, -1, 0)
    t = ((1-sy)*((1-sx)*z[0, 0]+sx*z[0, 1]) + sy*((1-sx)*z[1, 0]+sx*z[1, 1]))
    t -= t.mean(1, keepdims=True)
    corr = (t @ actual) / np.maximum(1e-12, np.linalg.norm(actual)*np.linalg.norm(t, axis=1))
    i = np.argmax(corr)
    delta = np.array([dx.ravel()[i], dy.ravel()[i]])
    q = float(corr[i])
    return dict(src=[x, y], xy=(center+delta).tolist(), ncc=round(q, 6),
                accepted=bool(q >= .75 and max(abs(delta)) < 5))


def fit(land):
    accepted = [m for m in land if m['accepted']]
    if len(accepted) < 6:
        raise ValueError('insufficient accepted training corners')
    lhs, rhs = [], []
    for m in accepted:
        x, y = m['src']
        u, v = m['xy'] - ORIGIN  # center output coordinate to improve conditioning
        lhs.extend(([x, y, 1, 0, 0, 0, -u*x, -u*y],
                    [0, 0, 0, x, y, 1, -v*x, -v*y]))
        rhs.extend((u, v))
    h, _, rank_, _ = np.linalg.lstsq(lhs, rhs, rcond=None)
    if rank_ != 8:
        raise ValueError('degenerate training geometry')
    return np.append(h, 1.).reshape(3, 3)


def project(h, xy):
    p = h @ [*xy, 1]
    if abs(p[2]) < 1e-9:
        raise ValueError('point at infinity')
    return ORIGIN + p[:2]/p[2]


def band_pitch(land, rows):
    out = []
    for a in land:
        for b in land:
            x, y = a['src']
            X, Y = b['src']
            if a['accepted'] and b['accepted'] and y in rows and y == Y and X-x >= 2:
                out.append(np.linalg.norm(np.subtract(b['xy'], a['xy']))/(X-x))
    return dict(pairs=len(out), median_px=float(np.median(out)) if out else None)


def run(raw):
    hashes = json.loads((BASE / 'private_evidence_hashes.json').read_text())
    inputs = {}
    for n in ('A10', 'B0', 'B1'):
        p = raw / f'{n}.png'
        if hashlib.sha256(p.read_bytes()).hexdigest() != hashes[p.name]:
            raise ValueError(f'incorrect archive input {n}')
        with Image.open(p) as img:
            if img.size != (1080, 2392):
                raise ValueError('preview dimensions')
            im = np.asarray(img.convert('RGB'), dtype=float) @ [.2126, .7152, .0722]
        inputs[n] = [locate(im, x, y, z) for x, y, z in corners(code(n[0]), int(n[0]=='B'))]
    h = fit(inputs['A10'])
    segments = [project(h, (6,y))-project(h, (2,y)) for y in (1,7)]
    detail = {}
    for n in ('B0', 'B1'):
        marks = inputs[n]
        resid, prior, bottom = [], [], []
        for m in marks:
            if m['accepted']:
                q = m['src']
                m['resid_px'] = float(np.linalg.norm(m['xy']-project(h, q)))
                resid.append(m['resid_px'])
                prior.append(np.linalg.norm(m['xy'] - (ORIGIN+BASIS@q)))
                if q[1] >= 6:
                    bottom.append(m['resid_px'])
        detail[n] = dict(eligible=len(marks),accepted=len(resid),max_px=max(resid, default=None),
                         rms_px=float(np.sqrt(np.mean(np.square(resid)))) if resid else None,
                         prior_max_px=float(max(prior)) if prior else None,
                         all_under_2px=(len(resid)>=6 and len(resid)==len(marks) and max(resid)<=2),
                         top=band_pitch(marks,(1,2)),bottom=band_pitch(marks,(6,7)),
                         bottom_tested=len(bottom),bottom_max_px=max(bottom, default=None))
    return dict(r025=r025(), train='A10, even-parity internal corners', test=detail,
                landmarks=inputs, h_relative_to_origin=h.tolist(),
                fitted_pitch_top_bottom=[float(np.linalg.norm(v)/4) for v in segments],
                four_cell_vectors_px=[v.tolist() for v in segments],
                anchored_transfer_difference_px=float(np.linalg.norm(segments[1]-segments[0])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('private_r10', type=Path)
    print(json.dumps(run(parser.parse_args().private_r10), indent=2, allow_nan=False))
