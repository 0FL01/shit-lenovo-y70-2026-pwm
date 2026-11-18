"""Audit archived R12b. No device access; stdout contains no images or private paths."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

NAMES = [f'p{i:02d}_{j}.png' for i in range(1, 7) for j in range(1, 4)]


def read(path):
    return json.loads(path.read_bytes())


def sha(b):
    return hashlib.sha256(b).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class InMemoryPNG:
    name = 'shifted.png'

    def __init__(self, im):
        buf = io.BytesIO()
        im.save(buf, format='PNG', compress_level=1)
        self.b = buf.getvalue()

    def read_bytes(self):
        return self.b


def firsts(keys):
    seen = set()
    keep = []
    for i, k in enumerate(keys):
        if k not in seen:
            keep.append(i)
        seen.add(k)
    return keep


def run(root, frames):
    src = read(root/'source/outcome_r12b.json')
    ref = read(root/'analysis/outcome.json')
    key = read(root/'analysis/revealed_codes.json')
    geom = {g['name']:g['checks']['pass_witness'] for g in read(root/'geometry/actual_capture.json')}
    predict = module('r12_predict', root/'analysis/predict.py')
    score = module('r12_score', root/'analysis/score.py')
    if set(geom) != set(NAMES) or sorted(p.name for p in frames.iterdir()) != NAMES:
        raise ValueError('exactly 18 input previews & witnesses required')
    byop = {v['ordinal']:v for v in src['frames']}
    base, full, roi, off = {}, [], [], []
    ctl, brackets = {}, []
    for n in NAMES:
        phase, take = int(n[1:3]), int(n[4])
        o = byop[f'P{phase-1:02d}_{take-1}']
        p = frames/n
        base[n] = predict.extract(p)
        if base[n]['hash'] != o['image']['sha256']:
            raise ValueError(f'operator/preview binding: {n}')
        with Image.open(p) as png:
            im = png.convert('RGB')
        a = np.asarray(im)
        full.append(sha(a.tobytes()))
        roi.append(sha(a[910:1335,900:1080][predict.mask].tobytes()))
        # At original grid x (900…1079), offset image supplies original x-800.
        # Cyclic wrap only matters outside sampled domain.
        shifted = ImageChops.offset(im, 800, 0)
        off.append(predict.extract(InMemoryPNG(shifted)))
        brackets.append([o['pre']['frame_offset'],o['post']['frame_offset']])
    replay = score.main(base, key)
    if replay != ref:
        raise ValueError('published scoring result not reproduced')
    # Exercise the frozen scorer rather than rewrite its decoys, margin or rules.
    # Same off-screen feature presented at every phase; use four *individual*
    # code outputs, never its synthetic repeated-series summary.
    for n, item in zip(NAMES, off):
        res = score.main(dict.fromkeys(NAMES, item), key)['frames']
        cand = {k:res[f'p{key["order"].index(k)+1:02d}_1.png'] for k in 'CcDd'}
        ctl[n] = dict(calls=[k for k,m in cand.items() if m['ok']],
                      max_accuracy=max(m['accuracy'] for m in cand.values()),
                      max_abs_ncc=max(abs(m['ncc']) for m in cand.values()),
                      gap=item['gap'], endpoints=item['endpoints'])
    unique = firsts(full)
    frame_ok = [replay['frames'][n]['ok'] for n in NAMES]
    code = [n for n in NAMES if 'accuracy' in replay['frames'][n]]
    inv = [x['ok'] for x in replay['inversions'].values()]
    return {
        'R019':dict(planned=18, available=len(full), retained_after_rgb_dedup=len(unique),
                    duplicate_slots=[n for i,n in enumerate(NAMES) if i not in unique],
                    unique_full_rgb=len(set(full)), unique_central_1280_rgb=len(set(roi)),
                    unique_png=len(set(v['hash'] for v in base.values())),
                    distinct_service_offsets=len(set(x for b in brackets for x in b)),
                    strictly_increasing_offsets=all(a<b for a,b in zip(sum(brackets,[])[:-1],sum(brackets,[])[1:])),
                    displayed_sensor_frame_id='unknown',
                    original_signal_series_pass=replay['decoder_pixel_pass'],
                    after_dedup=('incomplete' if len(unique)<18 else replay['decoder_pixel_pass'])),
        'R020':dict(independent_completed_series=1, series_pass=int(all(frame_ok) and all(inv) and all(geom.values())),
                    coded_signal_pass=sum(replay['frames'][n]['ok'] for n in code), coded_total=len(code),
                    null_pass=sum(replay['frames'][n]['ok'] for n in NAMES if n not in code), null_total=18-len(code),
                    geometric_pass=sum(geom.values()), geometric_total=len(geom),
                    joint_coded_pass=sum(geom[n] and replay['frames'][n]['ok'] for n in code),
                    inversion_pass=sum(inv), inversion_total=len(inv), request_matches_R11=src['frozen_R11_request_matches']),
        'R021':dict(control_shift_xy=[-800,0], planned=18, analysed=len(ctl),
                    candidates_per_frame=4, false_call_frames=sum(bool(x['calls']) for x in ctl.values()),
                    endpoint_free_frames=sum(x['endpoints']==0 for x in ctl.values()), frames=ctl)
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,help='R12b evidence directory')
    parser.add_argument('previews',type=Path,help='private archive of 18 ordinal PNGs')
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.previews), indent=2, allow_nan=False))
