"""Offline R037–039; stdout contains derived scalars only. No device or network I/O."""
import argparse
import csv
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'artifacts'
sys.path.insert(0, str(ROOT / '06-tools/scope_pwm'))
import scope_divergence as div
from scope_pwm import Calibration, Unresolved, measure

BOX = (180, 400, 550, 545)
PHASES = ('1A', '2B', '3A', '4B', '5A')


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def r(x):
    return round(float(x), 6)


def doublet(second, height):
    unit = np.zeros(48, dtype=int)
    unit[:7] = 40
    unit[second:second+7] = height
    period = next(k for k in range(1, 49) if np.array_equal(unit, np.roll(unit, k)))
    signal = np.roll(np.tile(unit, 8), 5)
    im = Image.new('RGB', (len(signal), 80))
    for i, z in enumerate(signal):
        im.putpixel((i, 60-int(z)), (255,255,255))
    out = {'gap_px': second, 'second_height_px': height, 'minimal_period_px': period}
    try:
        result = measure(im, (0,0,*im.size), (255,255,255), 0, Calibration(1,1,1,1))
    except Unresolved as e:
        return {**out, 'edge_px': None, 'refusal': str(e)}
    return {**out, 'edge_px': r(result['period_px']), 'cycle_variation_flag': result['cycle_variation_detected'],
            'detector_fundamental': result['waveform_fundamental_hz']}


def scope_states(src):
    base = ART/'scope_calibration_20261118'
    manifest = rows(base/'frames.csv') + rows(base/'sleep_frames.csv')
    ref = {x['original']: x for x in rows(ART/'scope_divergence_20261118/frames.csv')}
    if len(manifest) != 30 or len(set(x['original_basename'] for x in manifest)) != 30:
        raise ValueError('unexpected calibration manifest')
    out = []
    for row in manifest:
        tag = row['original_basename']
        if Path(tag).name != tag:
            raise ValueError('invalid basename')
        path = src/tag
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('wrong calibration original: '+tag)
        threshold, masks = div.profiles(div.crop_red(path))
        occ = list(map(r, masks.mean(axis=1))) if masks is not None else [None, None]
        old = ref[tag]
        if old['phase'] != row['phase'] or threshold != float(old['red_threshold']) or occ != [
            r(old[k]) if old[k] else None for k in ['upper_fraction','lower_fraction']]:
            raise ValueError('published profile not reproduced: '+tag)
        out.append(dict(phase=row['phase'], frame=tag, threshold=threshold, upper=occ[0], lower=occ[1]))
    if Counter(x['phase'] for x in out) != dict.fromkeys(
        'w1 blk w2 hi w3 lockwhite before off after restored'.split(),3):
        raise ValueError('unexpected scene sample sizes')
    return out


def metrics(a,b):
    """First distance for the scope and two exterior descriptors, all unsigned-code-safe."""
    return (div.distances(a[0],b[0])[0], np.abs(a[1]-b[1]).mean(), abs(a[1].mean()-b[1].mean()))


def spatial(src):
    manifest = rows(ART/'scope_spatial_divergence_20261118/frames.csv')
    if [row['capture'] for row in manifest] != [f'spatial-{ph}-{i}' for ph in PHASES for i in (1,2,3)]:
        raise ValueError('unexpected spatial manifest')
    hashes = rows(Path(__file__).with_name('spatial_v2_sha256.csv'))
    if [x['frame'] for x in hashes] != [x['capture']+'.png' for x in manifest]:
        raise ValueError('incomplete or reordered spatial hash manifest')
    data, reports, labels = [], [], []
    for row, pinned in zip(manifest, hashes, strict=True):
        tag, ph = row['capture'], row['phase']
        path = src/(tag+'.png')
        if hashlib.sha256(path.read_bytes()).hexdigest() != pinned['sha256']:
            raise ValueError('wrong spatial original: '+tag)
        threshold, masks = div.profiles(div.crop_red(path))
        if masks is None or threshold != float(row['ref_threshold']) or not np.allclose(
            masks.mean(axis=1), [float(row[k]) for k in ['upper_fraction','lower_fraction']], rtol=0,atol=1e-12):
            raise ValueError('spatial frame does not reproduce named reference: '+tag)
        with Image.open(path) as im:
            a = np.array(im.convert('RGB').crop(BOX), dtype=np.int16)
        data.append((div.descriptor(masks),a))
        labels.append(ph)
        reports.append(dict(frame=tag, phase=ph, mean=r(a.mean()), floor=r(np.mean(a==0)),
                            ceiling=r(np.mean(a==255)), p95_minus_p05=r(np.ptp(np.percentile(a,[5,95]))),
                            plus10pct_mae=r(np.abs(np.clip(np.rint(1.1*a),0,255)-a).mean())))
    names = ['trace_D','outside_MAE','outside_abs_mean_delta']
    by = {'same': [], 'different': []}
    for i,j in itertools.combinations(range(len(data)),2):
        by['same' if labels[i][-1]==labels[j][-1] else 'different'].append(metrics(data[i],data[j]))
    return {'outside_roi_ltrb':BOX,'frames':reports, 'n_pairs':{k:len(v) for k,v in by.items()},
            'scores':{k: {'same_max':r(np.max(np.array(by['same'])[:,i])),
                           'different_min':r(np.min(np.array(by['different'])[:,i])),
                           'gap': r(np.min(np.array(by['different'])[:,i])-np.max(np.array(by['same'])[:,i]))}
                      for i,k in enumerate(names)},
            'phase_median_outside_mean':{p:r(np.median([x['mean'] for x in reports if x['phase']==p])) for p in PHASES}}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('calibration_png_dir', type=Path)
    ap.add_argument('spatial_v2_png_dir', type=Path)
    args = ap.parse_args()
    print(json.dumps({'R037':[doublet(s,h) for s in (24,18) for h in (40,38,32,20)],
                      'R038':scope_states(args.calibration_png_dir),'R039':spatial(args.spatial_v2_png_dir)},
                     indent=2,allow_nan=False))
