#!/usr/bin/env python3
"""R47: python3 -B width.py FRAMES > width.csv
Archive check: python3 -B width.py --r44-control R44_LONGPASS/frames

One row per independent day_off{A,B,C}_{125,200,312}__N.dng release. A 500-us
group is included on each leg where acquired. Each group must start at 1 with
at least three contiguous releases; counts and optical phases need not match.
The bracket leg labels acquisition order, not a measured DBV or panel state.
The archived R44 high-drive OFF/ON/return control retains its own state names.

Use R46's two-front fit unchanged: fixed G1 ROI, signed DN, local >=20 DN on
both flanks in the full ROI and each half, same anchor, native support and
cross-half agreement. A failed gate leaves the width blank. Width is in RAW
rows, not panel off-time. No optical phases means no result (no CSV emitted).
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r46_20261121.width import FIELDS, US, frame, inputs


def analyze(directory, control=False):
    paths, seen = inputs(directory), set()
    states = ('off', 'on', 'ret') if control else ('offA', 'offB', 'offC')
    source = 'R44_day_high' if control else 'R47'
    for leg, state in zip('ABC', states):
        for token in ('125', '200', '312', '500'):
            phase = f'day_{state}_{token}'
            ns = sorted(n for ph, n in paths if ph == phase)
            if token == '500' and not ns:
                continue
            if len(ns) < 3 or ns != list(range(1, len(ns)+1)):
                raise ValueError(f'{source} {phase}: expected contiguous releases 1..N, N >= 3; got {ns}')
            for n in ns:
                path = paths[phase, n]
                try:
                    row = frame(path, US[token], seen)
                except ValueError as exc:
                    raise ValueError(f'{path.name}: {exc}') from exc
                yield dict(source=source, bracket_leg=leg, state=state, phase=phase,
                           frame_n=n, exposure_us=US[token], **row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--r44-control', action='store_true', help='use the accepted archival R44 daytime high-drive series')
    args = ap.parse_args()
    try:
        rows = list(analyze(args.frames, args.r44_control))
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, ['source', 'bracket_leg', *FIELDS], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
