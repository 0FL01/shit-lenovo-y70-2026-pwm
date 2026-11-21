#!/usr/bin/env python3
"""R45 low-PQ OFF optical pilot: python3 -B pilot.py FRAMES

Require cal_offLow_1250__{1,2}.dng and at least three distinct
day_offLow_{200,312,500}__N.dng per shutter (312 means 312.5 us).
Only a clipped 1250 us CAL may be replaced by a passing cal_offLow_500 pair.
Exit 0 (ALLOW_ON) requires passing guarded geometry and at least one short
shutter with every G1 ROI mean >=20 DN above tagged black and no G1 rails.
No broad event is required. Other scenes are ignored. Counts/ranges go to
stdout as CSV; the optical decision goes to stderr. This does not toggle ON.
"""

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import TOP, BOTTOM, LEFT, RIGHT, ROI, read_native
from direct_camera_r43_20261121.measure import EXPOSURES, sample
from direct_camera_r44_20261121.geometry import qualify


SHORT = ('200', '312', '500')
NAME = re.compile(r'(cal|day)_offLow_(\d+)__([1-9][0-9]*)\.dng', re.ASCII)


def inventory(frames):
    groups = defaultdict(dict)
    for path in sorted(frames.iterdir()):
        if not path.name.startswith(('cal_offLow_', 'day_offLow_')) or path.suffix.lower() not in ('.dng', '.partial'):
            continue
        m = NAME.fullmatch(path.name)
        if not m or path.is_symlink() or not path.is_file():
            raise ValueError(f'invalid or unfinished pilot frame: {path.name}')
        group, shutter, n = m.groups()
        if shutter not in (('1250', '500') if group == 'cal' else SHORT):
            continue
        groups[group, shutter][int(n)] = path
    return groups


def geometry(groups, seen):
    cal = {}
    for shutter in ('1250', '500'):
        pair = groups['cal', shutter]
        if not pair and shutter == '500':
            continue
        if pair.keys() != {1, 2}:
            cal[shutter] = 'INCOMPLETE_PAIR'
            continue
        rows = qualify('offLow', int(shutter), pair, seen)
        cal[shutter] = next((r['status'] for r in rows if r['status'] != 'PASS'), 'PASS')
    if cal == {'1250': 'CLIPPED', '500': 'PASS'}:
        return True, 'CLIPPED_REPLACED_BY_500'
    return all(s == 'PASS' for s in cal.values()), ';'.join(f'{k}:{v}' for k, v in cal.items())


def signal(path, us, seen):
    raw, black, white = read_native(path, us)
    # Same native-patch identity as R44 qualify(), also across CAL and DAY.
    patch = raw[2*TOP:2*BOTTOM, 2*LEFT:2*RIGHT]
    digest = blake2b(patch.tobytes(), digest_size=16).digest()
    if digest in seen:
        raise ValueError('duplicate native RAW patch')
    seen.add(digest)
    y0, y1, x0, x1 = ROI
    _, stats = sample(raw[2*y0:2*y1:2, 2*x0:2*x1:2], black, white, control=False)
    return stats


def run(frames):
    groups, seen = inventory(frames), set()
    geo_ok, cal_status = geometry(groups, seen)
    rows = []
    for shutter in SHORT:
        us = EXPOSURES[shutter]
        counts, means = Counter(), []
        for path in groups['day', shutter].values():
            try:
                stats = signal(path, us, seen)
            except ValueError as exc:
                raise ValueError(f'{path.name}: {exc}') from None
            means.append(stats['mean_dn'])
            counts[stats['gate']] += 1
        rows.append(dict(exposure_us=us, frames=len(means), signal_ok=counts['ok'],
                         below_20dn=counts['below_20dn'], clipped=counts['clipped'],
                         storage_floor=counts['storage_floor'],
                         mean_dn_min=f'{min(means):.6f}' if means else '',
                         mean_dn_max=f'{max(means):.6f}' if means else '', geometry=cal_status,
                         shutter_pass=int(geo_ok and counts['ok'] == len(means) >= 3)))
    allow = all(r['frames'] >= 3 for r in rows) and any(r['shutter_pass'] for r in rows)
    return rows, allow


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    args = ap.parse_args()
    try:
        rows, allow = run(args.frames)
    except (ValueError, OSError) as exc:
        ap.exit(1, f'HOLD_OFF: {exc}\n')
    out = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)
    print('ALLOW_ON' if allow else 'HOLD_OFF', file=sys.stderr)
    return 0 if allow else 1


if __name__ == '__main__':
    sys.exit(main())
