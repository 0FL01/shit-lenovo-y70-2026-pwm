"""Summarize published measurements, never access devices. Python standard library."""
import csv
import itertools
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ORDER = (2632, 2632, 2633, 2632, 2631, 2632, 2633, 2634, 2633, 2632, 2633, 2633, 2634, 2633)
LABELS = [f'{p}{i}' for p in ('off', 'on', 'return') for i in range(1, 4)]
VARIANTS = {(18,0,0), (12,0,0), (24,0,0), (18,-3,0), (18,3,0), (18,0,-3), (18,0,3)}


def rows(path):
    with (BASE / path).open() as f:
        return list(csv.DictReader(f))


def load(path):
    return json.loads((BASE / path).read_text())


def boundary(data):
    by_variant = {}
    expected = set(itertools.combinations_with_replacement(range(len(ORDER)), 2))
    for row in data:
        key = tuple(int(row[k]) for k in ('threshold', 'dx', 'dy'))
        lookup = {f'P{i:02d}': i for i in range(len(ORDER))}
        a, b = lookup[row['a']], lookup[row['b']]
        group = by_variant.setdefault(key, {})
        value = float(row['Dmed'])
        if (a, b) in group or int(row['n']) != (3 if a == b else 9) or not 0 <= value <= 1:
            raise ValueError('duplicate pair, bad count, or invalid D')
        group[a, b] = value
    if set(by_variant) != VARIANTS:
        raise ValueError('missing or unexpected variants')
    out = {}
    for key, group in sorted(by_variant.items()):
        if set(group) != expected:
            raise ValueError('partial or unexpected phase pair')
        sets = {k: [] for k in ('boundary', 'sham', 'lower', 'upper')}
        for i, (a, b) in enumerate(zip(ORDER, ORDER[1:])):
            kind = 'sham' if a == b else {2631:'lower', 2632:'boundary', 2633:'upper'}[min(a, b)]
            sets[kind].append(group[i, i+1])
        targets = sets['boundary']
        controls = sets['sham'] + sets['lower'] + sets['upper']
        out[','.join(map(str,key))] = {
            'Dmed_ranges': {k: [len(v), min(v), max(v)] for k,v in sets.items()},
            'strict_wins_over_controls': sum(x > y for x in targets for y in controls),
            'comparisons': len(targets)*len(controls),
            'min_boundary_minus_max_control': round(min(targets)-max(controls), 6)}
    return out


def extra_dim(frames, obs):
    if [r['frame'] for r in frames] != LABELS or [r['label'] for r in obs['photos']] != LABELS:
        raise ValueError('incomplete or swapped phases')
    camera = obs['camera2']
    if not obs['target_scene_equal_720x1584'] or not obs['restore_target'] or not obs['restore_camera_controls']:
        raise ValueError('unsupported scene/return')
    for r,p in zip(frames, obs['photos']):
        if (int(r['ISO']) != int(camera['sensor.sensitivity'])
            or round(float(r['exposure_s'])*1e9) != int(camera['sensor.exposureTime'])
            or not math.isclose(float(r['bright_fraction_R_gt192']),p['bright_red_pixel_fraction'],abs_tol=0.000501)):
            raise ValueError('preview/EXIF or archive summary mismatch')
    groups = {p:[float(r['bright_fraction_R_gt192']) for r in frames if r['frame'].startswith(p)]
              for p in ('off','on','return')}
    margin = min(groups['off']+groups['return']) - max(groups['on'])
    return {'phase_ranges': {k:[min(v),max(v)] for k,v in groups.items()},
            'minimum_off_or_return_minus_max_on':round(margin,6),
            'ISO':int(camera['sensor.sensitivity']), 'exposure_ns':int(camera['sensor.exposureTime']),
            'preview_reads_missing_timestamp':sum(int(r['preview_reads_missing_ts']) for r in frames),
            'AWB_lock':camera['control.awbLock']}


def run():
    first = load('STOCK_EXTRA_DIM_20261118_data.json')['photos']
    return {
        'R079_adjacent_transitions_only':boundary(rows('stock_dbv_r7_ordinal_20261118/results/ordinal_pairs.csv')),
        'R080_first_round_EXIF_ISO':{r['phase']:r['exif']['iso'] for r in first},
        'R080_locked_round':extra_dim(rows('extra_dim_round2_raster_audit_20261118/derived/frames.csv'),
            load('stock_extra_dim_locked_20261118/observations.json')),
        'R081_model_only':{str(c):{'normalized_code':round(c/255,6),
            'sRGB_decoded_linear':round(((c/255+0.055)/1.055)**2.4,6)} for c in (133,191)}
    }


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
