#!/usr/bin/env python3
"""R49: python3 -B field.py FRAMES --orientation 6 --us 25000 > field.csv

Use dedicated white/512 CALs: cal_{A,B,R}_25000__N.dng. Take three or four
independent releases per phase, with the same count throughout; pin a planned
count with --releases. expected_dbv is a schedule label, not readback. R49
requires Orientation 6; 1 is for archive checks only. Neither rotates the CFA.

The fixed G1 ROI is y=[630,1250), x=[754,799) in 2x2 cells. R43 tests the
entire 20-cell guard with horizontal 9-cell medians, a 20 DN absolute floor
and relative field/row/local thresholds for shading. R48 extends this test to
multiple releases: every guard row needs full-width support in at least one
release, every release needs >=70% lit rows in each quarter, no lateral
intrusion on a lit row, and no stored floor or clip on ANY guarded CFA site.

This diagnoses usable illumination, not exact registration on a featureless
field. LOW_SIGNAL means all guard p75s are below 20 DN, not a black panel or
an unchanged panel. Means are retained for rail/field failures. Never gate a
short science exposure or black control as a white CAL, or require a change,
matched brightness, or a return to baseline to pass this geometry test.

Historical check at these exact coordinates (R34, tagged Orientation 1):
a01_activeFlat__{1,2,3} (0x8e, white/512, 25 ms) had ROI means 185.94 to
186.23 DN over tagged black, zero rails and full coverage. a02_activeBlack
had 0.22 to 0.25 DN, zero rails but all 660 rows unsupported. These are
positive/negative field controls, not R49 CALs or brightness targets.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import GUARD, X0, X1, Y0, Y1, capture
from direct_camera_r48_20261121.field import FIELDS, qualify
from direct_camera_r48_20261121.measure import native_orientation


CAL = re.compile(r'cal_([ABR])_25000__([1-4])\.dng')


def inventory(frames):
    groups = {s: {} for s in 'ABR'}
    for path in sorted(frames.iterdir()):
        if not path.name.startswith('cal_'):
            continue
        m = CAL.fullmatch(path.name)
        if not m or path.is_symlink() or not path.is_file():
            raise ValueError(f'invalid or unfinished CAL: {path.name}')
        groups[m[1]][int(m[2])] = path
    return groups


def field(state, files, n, us, orientation, seen):
    phase = f'cal_{state}_{us}'
    base = dict(phase=phase, scene=state, expected_dbv=512, exposure_us=us,
                required_orientation=orientation, n_required=n, n_present=len(files),
                y0=Y0, y1=Y1, x0=X0, x1=X1, guard=GUARD)
    expected = set(range(1, n+1))
    if files.keys() != expected:
        rows = [dict(status='INVALID_RELEASES', detail=f'expected {sorted(expected)}, found {sorted(files)}')]
    else:
        try:
            caps = [capture(files[i], us, seen) for i in sorted(files)]
            rows = qualify(caps)
        except (OSError, ValueError) as exc:
            rows = [dict(status='INVALID_CAL', detail=str(exc))]
        else:
            if rows[0].get('quarter') and all(rows[0][f'field_p75_dn{i}'] < 20 for i in files):
                for row in rows:
                    row.update(status='LOW_SIGNAL', detail='guard p75 below 20 DN in every release')
    status = next((r['status'] for r in rows if r['status'] != 'PASS'), 'PASS')
    for row in rows:
        yield dict(base, state_status=status, **row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--orientation', choices=(1, 6), type=int, default=6,
                    help='required TIFF Orientation (default 6; 1 for historical input)')
    ap.add_argument('--us', choices=(25000,), type=int, default=25000)
    ap.add_argument('--releases', choices=(3, 4), type=int,
                    help='exact count per phase (default 4 if any fourth CAL exists, else 3)')
    args = ap.parse_args()
    try:
        groups = inventory(args.frames)
    except (OSError, ValueError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    n = args.releases or (4 if any(4 in g for g in groups.values()) else 3)
    out = csv.DictWriter(sys.stdout, (*FIELDS, 'required_orientation'), lineterminator='\n')
    out.writeheader()
    seen, failed = set(), False
    with native_orientation(args.orientation):
        for state, files in groups.items():
            for row in field(state, files, n, args.us, args.orientation, seen):
                out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})
                failed |= row['state_status'] != 'PASS'
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
