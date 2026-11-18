"""Offline preview geometry, synthetic resampling and RGB cell contrast; no device IO."""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'stock_blind_static_r12_20261118'
NAMES = [f'p{p:02}_{s}.png' for p in range(1, 7) for s in range(1, 4)]


def read(path):
    return json.loads(path.read_bytes())


def match(a, b, box, search=6):
    """Integer a->b translation by zero-mean NCC; no wrap at crop edges."""
    x, y, X, Y = box
    if a.shape != b.shape or not (search <= x < X <= a.shape[1]-search and
                                  search <= y < Y <= a.shape[0]-search):
        raise ValueError('invalid search domain')
    t = a[y:Y, x:X] - a[y:Y, x:X].mean()
    tn = np.linalg.norm(t)
    scores = []
    for dx in range(-search, search+1):
        for dy in range(-search, search+1):
            w = b[y+dy:Y+dy, x+dx:X+dx]
            w = w-w.mean()
            den = tn*np.linalg.norm(w)
            scores.append((float(np.sum(t*w)/den) if den else 0., dx, dy))
    score, dx, dy = max(scores)
    gap = score-max(s for s, i, j in scores if max(abs(i-dx), abs(j-dy)) > 1)
    ok = score >= .90 and max(abs(dx), abs(dy)) < search and gap >= .01
    return dict(dx=dx, dy=dy, ncc=round(score, 6), gap=round(gap, 6), resolved=bool(ok))


def geometry(a, b, boxes):
    out = [match(a, b, box) for box in boxes]
    value = np.array([[w['dx'], w['dy']] for w in out])
    return dict(boxes=boxes, matches=out,
                tile_minus_each_anchor_xy=(value[2:, None]-value[None, :2]).tolist(),
                common_compatible=bool(all(w['resolved'] for w in out) and
                                       max(np.ptp(value, axis=0)) <= 2))


def raster(k, period):
    cases = []
    n = 192
    expected = n//period  # integer cycles, before aliasing
    for phase in range(4):
        for start in range(k):
            s = np.sin((np.arange(n)+start)*2*np.pi/period+phase*np.pi/2)
            w = s.reshape(-1, k).mean(axis=1)
            amp = float(np.ptp(w)/2)
            fft = abs(np.fft.rfft(w-w.mean()))
            peak = int(np.argmax(fft)) if fft.max() > 1e-8 else None
            cases.append((amp, peak))
    return dict(period=period, scale=k, n_cases=len(cases),
                min_span_fraction=round(min(v for v, _ in cases), 6),
                max_span_fraction=round(max(v for v, _ in cases), 6),
                visible_bins=sorted({i for _, i in cases if i is not None}),
                flat=sum(i is None for _, i in cases),
                resolved=bool(period > 2*k and all(v >= .3 and i == expected for v, i in cases)))


def contrast(rgb, code):
    if rgb.shape != (8, 8, 3) or code.shape != (8, 8) or not np.all(
            ((code == 1).sum(1) == 4) & ((code == -1).sum(1) == 4)):
        raise ValueError('expected balanced binary rows with RGB cells')
    rows = [np.median(row[m == 1], 0)-np.median(row[m == -1], 0)
            for row, m in zip(rgb, code)]
    return np.median(rows, axis=0)


def run(frames):
    spec = importlib.util.spec_from_file_location('frozen_predict', ROOT/'analysis/predict.py')
    predictor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(predictor)
    key = read(ROOT/'analysis/revealed_codes.json')
    if key['order'] != ['d', 'C', 'D', 'c', 'U', 'C']:
        raise ValueError('unexpected phase order')
    manifest = {r['ordinal']: r['image']['sha256']
                for r in read(ROOT/'source/outcome_r12b.json')['frames']}
    signals = read(ROOT/'analysis/outcome.json')['frames']
    witnesses = {r['name']: r['checks']['pass_witness']
                 for r in read(ROOT/'geometry/actual_capture.json')}
    if sorted(p.name for p in frames.iterdir()) != NAMES or len(set(manifest.values())) != 18:
        raise ValueError('unexpected file set or repeated source')
    colors = {}
    for i, name in enumerate(NAMES):
        z = predictor.extract(frames/name)
        if z['hash'] != manifest[f'P{i//3:02}_{i%3}']:
            raise ValueError('slot digest mismatch: '+name)
        k = key['order'][i//3]
        mask = np.array(key['C' if k == 'U' else k.upper()]) * (-1 if k.islower() else 1)
        diff = contrast(np.array(z['rgb']), mask)
        colors[name] = dict(code=k, median_row_delta_rgb=diff.tolist(),
                            original_signal_pass=signals[name]['ok'],
                            original_geometry_pass=witnesses[name])
    pair = [frames/n for n in ('p02_1.png', 'p06_1.png')]
    imgs = []
    for path in pair:
        with Image.open(path) as im:
            imgs.append(np.asarray(im.convert('RGB')).mean(axis=2))
    boxes = read(ROOT/'geometry/freeze.json')['boxes'] + [
        [x, y, x+36, y+32] for y in (1100, 1132) for x in (922, 958)]
    real = np.array([r['median_row_delta_rgb'] for r in colors.values() if r['code'] != 'U'])
    sham = np.array([r['median_row_delta_rgb'] for r in colors.values() if r['code'] == 'U'])
    return dict(R028=dict(pair=[p.name for p in pair], **geometry(*imgs, boxes)),
                R029=[raster(k, p) for k in (1, 2, 3, 4) for p in (2, 3, 4, 6, 8, 12, 16)],
                R030=dict(per_frame=colors, coded_min=real.min(0).tolist(),
                          coded_max=real.max(0).tolist(), sham_abs_max=abs(sham).max(0).tolist(),
                          all_above_sham=(real.min(0) > abs(sham).max(0)).tolist()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=Path, help='exact 18 ordinal R12b PNGs')
    print(json.dumps(run(parser.parse_args().frames), indent=2, allow_nan=False))
