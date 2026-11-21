#!/usr/bin/env python3
"""R47: python3 -B field.py FRAMES --us 1250 --states offA offB offC > field.csv

One invocation tests one exact CAL shutter for every listed state. Use --states
offA for the quick pilot: also require an independent day_offA short shutter
with mean G1 >=20 DN above black and no stored rails in every available release
at that shutter. Short counts and the pilot decision are written to stderr.

R44 Y'=573 / BL 13119 / HDR:SDR 4.2909: both OFF CALs passed at 1250 us;
the brightest stored site in the guard was 602 (black 63.79, white 1023).
Only ~1.78x more net peak signal would reach the rail at the same shutter.
The Android ratio is not a camera exposure multiplier. Keep a clipped 1250-us
result and explicitly rerun --us 500 with fresh pairs for ALL compared states.
Do not mix shutters or rescue a floor, missing pair or shadow by relabeling it.
4000 us is optional, for an independently planned low-light field check only.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import GUARD, capture
from direct_camera_r43_20261121.measure import EXPOSURES
from direct_camera_r44_20261121.geometry import FIELDS, qualify


STATES = ('offA', 'offB', 'offC')
SHORT = ('125', '200', '312', '500')  # acquisition token 312 is exactly 312.5 us


def releases(frames, phase):
    result = {}
    for path in sorted(frames.glob(f'{phase}__*')):
        m = re.fullmatch(r'([1-9][0-9]*)\.dng', path.name.split('__', 1)[1])
        if not m or path.is_symlink() or not path.is_file():
            raise ValueError(f'invalid or unfinished release: {path.name}')
        result[int(m[1])] = path
    if set(result) != set(range(1, len(result) + 1)):
        raise ValueError(f'{phase}: gap in release numbers')
    return result


def field(frames, us, states, seen):
    rows = []
    for state in states:
        phase = f'cal_{state}_{us}'
        pair = releases(frames, phase)
        if pair.keys() != {1, 2}:
            raise ValueError(f'{phase}: expected independent __1 and __2 DNGs')
        rows.extend(qualify(state, us, pair, seen))
    return rows


def short_pilot(frames, seen):
    passed = False
    for token in SHORT:
        series = releases(frames, f'day_offA_{token}')
        if not series:
            continue
        means, clips, floors = [], 0, 0
        for path in series.values():
            g1, clip, floor = capture(path, EXPOSURES[token], seen)
            # capture() subtracts tagged G1 black and counts any-CFA stored rails
            # in the guarded rectangle. Brightness itself is for the fixed ROI.
            means.append(g1[GUARD:-GUARD, GUARD:-GUARD].mean())
            clips += clip
            floors += floor
        ok = not (clips or floors) and min(means) >= 20
        print(f'day_offA_{token}: n={len(means)} mean_dn={min(means):.3f}..{max(means):.3f} '
              f'clip={clips} floor={floors} {"PASS" if ok else "FAIL"}', file=sys.stderr)
        passed |= ok
    return passed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--us', type=int, choices=(1250, 500, 4000), required=True)
    ap.add_argument('--states', nargs='+', choices=STATES, default=STATES)
    args = ap.parse_args()
    if len(set(args.states)) != len(args.states):
        ap.error('duplicate state')
    seen = set()
    try:
        rows = field(args.frames, args.us, args.states, seen)
        out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
        out.writeheader()
        for row in rows:
            out.writerow({k: format(v, '.7g') if isinstance(v, float) else v for k, v in row.items()})
        cal_ok = all(r['status'] == 'PASS' for r in rows)
        if tuple(args.states) == ('offA',):
            short_ok = short_pilot(args.frames, seen)
            print(f'pilot A: CAL/{args.us}={"PASS" if cal_ok else "FAIL"} '
                  f'short={"PASS" if short_ok else "FAIL"}', file=sys.stderr)
            return int(not (cal_ok and short_ok))
        return int(not cal_ok)
    except (OSError, ValueError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')


if __name__ == '__main__':
    sys.exit(main())
