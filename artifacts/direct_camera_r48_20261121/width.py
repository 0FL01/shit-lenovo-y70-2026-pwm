#!/usr/bin/env python3
"""R48: python3 -B width.py FRAMES > width.csv

Four originals (__1.dng through __4.dng) per phase: day_off{A,B,C,D,Dr,Cr,Br,Ar}
at 125, 200 and 312.5 us (token 312), plus day_offBs_125 (fresh approach to
14056) and day_offQ_125 (immediate reissue of the same float). One row per RAW,
104 rows in total. CAL frames are not width samples.

R46's unchanged two-front G1 fit reports FWHM in RAW rows only if status=ok:
both observed crossings, native support, signal and agreement across the full
ROI and both halves. Failed fits retain their status and blank width. A width
describes an exposure-integrated image trough, not panel off-time.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r46_20261121.width import FIELDS, US, frame, inputs
from direct_camera_r48_20261121.measure import add_orientation, native_orientation


LEGS = ('A', 'B', 'C', 'D', 'Dr', 'Cr', 'Br', 'Ar')
SHUTTERS = ('125', '200', '312')


def analyze(directory, control=False):
    paths, seen = inputs(directory), set()
    groups = [(leg, token) for leg in (LEGS[:3] if control else LEGS) for token in SHUTTERS]
    if not control:
        groups.extend([('Bs', '125'), ('Q', '125')])
    for leg, token in groups:
        phase = f'day_off{leg}_{token}'
        ns = sorted(n for ph, n in paths if ph == phase)
        if ns != [1, 2, 3, 4]:
            raise ValueError(f'{phase}: expected four releases 1..4; got {ns}')
    for leg, token in groups:
        state = 'off' + leg
        phase = f'day_{state}_{token}'
        for n in range(1, 5):
            path = paths[phase, n]
            try:
                row = frame(path, US[token], seen)
            except ValueError as exc:
                raise ValueError(f'{path.name}: {exc}') from exc
            yield dict(bracket_leg=leg, state=state, phase=phase, frame_n=n,
                       exposure_us=US[token], **row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--r47-control', action='store_true', help='validate on the archived R47 A/B/C high-drive series')
    add_orientation(ap)
    args = ap.parse_args()
    try:
        with native_orientation(args.orientation):
            rows = list(analyze(args.frames, args.r47_control))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, ['bracket_leg', *FIELDS], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
