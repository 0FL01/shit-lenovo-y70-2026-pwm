#!/usr/bin/env python3
"""R48: python3 -B field.py FRAMES --us 312.5 > field.csv

For the resume archive supply --orientation 6 (default 1). This checks the
exact EXIF tag; the fixed ROI always uses unrotated native Bayer cells.
Use exactly cal_STATE_312__{1,2,3,4}.dng at 312.5 us by default. R43's
single-release levels, any-CFA rail counts and lateral test are unchanged.
Every guard row must be lit across its full width in >=1 of the four releases;
every release must independently illuminate >=70% of each quarter. --releases 2
is for historical two-release archives only; never take two out of four.
Repeat --us to report separate brackets, retaining every failure. Default:
offA..offD plus any acquired return/sham CAL labels. --states offA selects a
pilot; pass explicit states to also require a planned but missing return.
phase is the filename stem before __N, exposure_us the metadata-checked duration.
expected_dbv is a schedule label, not a hardware readback. status describes
one quarter (blank quarter on input/rail failure); state_status covers all four
quarters. G1 means use all releases, the unguarded R42 ROI and tagged black.
g1_mean_{min,max}_dn are the extrema of release means, not pixel extrema.
Use g1_mean_dn for brightness matching only on state_status=PASS.

Prior evidence, reread at these exact coordinates (native white 1023):
  R36 peak_200, white SDR / 14078: mean G1 432..439 DN above black; maximum
  stored guard site 740. Linear mean extrapolation to 500 us exceeds the
  ~959 DN available; even 312.5 us can clip peaks. R36 shots are not CALs.
  R43 cal_sdrHigh_500, SDR video Y'=721 / 13119: mean 490..491 DN, maximum
  guard site 766; both passed. R47 cal_off{A,B,C}_500, HDR / 16000..16001:
  mean 332..339 DN, maximum 597; CAL/500 passed and CAL/1250 clipped.
These are scene-specific headroom priors. Qualify fresh independent CALs
at one common shutter for all levels; do not move the ROI to rescue a failure.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import GUARD, LEFT, TOP, X0, X1, Y0, Y1, capture, levels
from direct_camera_r43_20261121.measure import EXPOSURES
from direct_camera_r48_20261121.measure import add_orientation, native_orientation


LEVELS = dict(zip(('offA', 'offB', 'offC', 'offD'), range(14055, 14059)))
OPTIONAL = ('offDr', 'offCr', 'offBr', 'offAr', 'offQ')
FIELDS = ('phase scene expected_dbv exposure_us n_required n_present y0 y1 x0 x1 guard '
          'state_status g1_mean_dn g1_mean_min_dn g1_mean_max_dn quarter first_y last_y '
          'uncovered_rows min_support_releases min_support_score worst_y worst_release '
          'worst_window_x0 status detail').split()
FIELDS += [f'{key}{i}' for key in ('g1_mean_dn', 'clip', 'floor', 'field_p75_dn', 'lit_frac', 'lateral_bad_rows')
           for i in range(1, 5)]


def numbered(key, values):
    return {f'{key}{i}': v for i, v in enumerate(values, 1)}


def qualify(caps):
    """All supplied releases participate in rail, field, and brightness checks."""
    means = [g[GUARD:-GUARD, GUARD:-GUARD].mean() for g, _, _ in caps]
    clips, floors = [c for _, c, _ in caps], [f for _, _, f in caps]
    base = dict(g1_mean_dn=np.mean(means), g1_mean_min_dn=min(means), g1_mean_max_dn=max(means),
                **numbered('g1_mean_dn', means), **numbered('clip', clips), **numbered('floor', floors))
    if any(floors) or any(clips):
        return [dict(base, status='FAIL_FLOOR' if any(floors) else 'CLIPPED')]

    scores, lateral_fail, p75 = zip(*(levels(g) for g, _, _ in caps))
    scores, lateral_fail = np.stack(scores), np.stack(lateral_fail)
    base.update(numbered('field_p75_dn', p75))
    whole_row = scores.min(axis=2)  # one release must illuminate BOTH corners and everything between
    lit = whole_row >= 1
    support_count = lit.sum(axis=0)
    support = whole_row.max(axis=0)
    rows = []
    for quarter, yy in enumerate(np.array_split(np.arange(len(support)), 4), 1):
        good = lit[:, yy].mean(axis=1)
        lateral = lateral_fail[:, yy].sum(axis=1)
        uncovered = np.count_nonzero(support_count[yy] == 0)
        ok = not uncovered and not lateral.any() and (good >= .70).all()
        # Argmax identifies a diagnostic location only; no pair is selected for grading.
        y = yy[np.argmin(support[yy])]
        i = np.argmax(whole_row[:, y])
        rows.append(dict(base, quarter=quarter, first_y=TOP+yy[0], last_y=TOP+yy[-1],
                         uncovered_rows=uncovered, min_support_releases=support_count[yy].min(),
                         min_support_score=support[y], worst_y=TOP+y, worst_release=i+1,
                         worst_window_x0=LEFT+np.argmin(scores[i, y]), status='PASS' if ok else 'FAIL_FIELD',
                         **numbered('lit_frac', good), **numbered('lateral_bad_rows', lateral)))
    return rows


def field(files, state, token, n, seen):
    phase = f'cal_{state}_{token}'
    names = {name for name in files if name.startswith(phase + '__')}
    ordered = [f'{phase}__{i}.dng' for i in range(1, n+1)]
    expected = set(ordered)
    us = EXPOSURES[token]
    dbv = 14056 if state == 'offQ' else LEVELS[state.removesuffix('r')]
    base = dict(phase=phase, scene=state, expected_dbv=dbv, exposure_us=us, n_required=n,
                n_present=len(expected & names), y0=Y0, y1=Y1, x0=X0, x1=X1, guard=GUARD)
    if names - expected:
        rows = [dict(status='INVALID_RELEASES', detail='unexpected: ' + ', '.join(sorted(names - expected)))]
    elif expected - names:
        rows = [dict(status='MISSING_RELEASES', detail='missing: ' + ', '.join(sorted(expected - names)))]
    else:
        try:
            caps = []
            for name in ordered:
                path = files[name]
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f'{name}: not an original regular file')
                caps.append(capture(path, us, seen))  # R43 verifies EXIF and rejects duplicate native patches
            rows = qualify(caps)
        except (OSError, ValueError) as exc:
            rows = [dict(status='INVALID_CAL', detail=str(exc))]
    state_status = next((r['status'] for r in rows if r['status'] != 'PASS'), 'PASS')
    for row in rows:
        yield dict(base, state_status=state_status, **row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    add_orientation(ap)
    ap.add_argument('--us', choices=('500', '312.5', '312', '200'), action='append',
                    help='CAL duration in microseconds (default 312.5; repeat for separate brackets)')
    ap.add_argument('--releases', type=int, choices=(2, 4), default=4,
                    help='exact independent CAL releases per state (default 4; 2 for historical archives)')
    ap.add_argument('--states', nargs='+', choices=(*LEVELS, *OPTIONAL), help='exact required CAL labels')
    args = ap.parse_args()
    tokens = ['312' if us == '312.5' else us for us in (args.us or ['312'])]
    try:
        files = {p.name: p for p in args.frames.iterdir() if p.name.startswith('cal_')}
    except OSError as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    states = args.states or [*LEVELS, *(s for s in OPTIONAL if any(n.startswith(f'cal_{s}_') for n in files))]
    if len(tokens) != len(set(tokens)) or len(states) != len(set(states)):
        ap.error('duplicate CAL duration or state')
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
    out.writeheader()
    seen, failed = set(), False
    with native_orientation(args.orientation):
        for token in tokens:
            for state in states:
                for row in field(files, state, token, args.releases, seen):
                    out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})
                    failed |= row['state_status'] != 'PASS'
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
