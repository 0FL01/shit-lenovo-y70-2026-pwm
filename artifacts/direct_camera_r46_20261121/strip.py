#!/usr/bin/env python3
"""R46 long timing strip: python3 -B strip.py FRAMES > strip.csv

ROI is (y0,y1,x0,x1) in half-open native Bayer cells. No rotation, resizing,
stitching or search on R46. The separate R45 amplitude ROI is unchanged.
CAL establishes an illuminated field at the camera, not display state or Hz.
One receipt per state; PASS only if all states pass. Use --quarters for the
per-release/quarter diagnostics. --field-us 4000 selects the independently
preregistered repeat bracket's 4 ms geometry pairs for ALL states; never use
these shutters for timing or mix CALs from different brackets. Default 1250
reports the original protocol (only a clipped pair can be replaced by 500).
Call require_geometry(frames, field_us) before processing R46 timing;
separately bind acquisition windows and qualify each short release.

Reproduce the design check: strip.py --r45-training R45_FRAMES. Selection
used ONLY R45: extend the R42 strip upward/downward and compare fixed x bands
away from the lower-right obstruction. Require all three 1250 us pairs to
pass the full R43 test and two ON DNGs at one short shutter with an adjacent
pair in the strip interior. Reserve 100 cells beyond the OUTER bounds of the
two runs (11 cells for smoothing/shoulders + ceil(177.35/2) cells for one
R35 control pitch). This is geometric clearance, not a pitch assigned to ON.
At 312.5 us, training frames 2 and 3 have 104 and 108 cells of clearance;
at 500 us the sole R43 gap is too close to the edge. Training never grants
R46 a CAL pass, identifies independent events in R46, or supplies its scale.
"""

import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import GUARD, WIDTH, levels, read_native


ROI = (580, 1365, 725, 790)
Y0, Y1, X0, X1 = ROI
TOP, BOTTOM, LEFT, RIGHT = Y0-GUARD, Y1+GUARD, X0-GUARD, X1+GUARD
SCENES = ('on120A', 'on144B', 'on120C')
TRAINING = ('offLow', 'onLow', 'retLow')
MARGIN = 100  # Bayer cells; 200 physical RAW rows
CAL = re.compile(r'cal_([A-Za-z0-9]+)_(1250|500|4000)__([12])\.dng')
ACCEPTED = ('PASS', 'CLIPPED_REPLACED_BY_500')
QUARTER_FIELDS = ('kind scene exposure_us y0 y1 x0 x1 guard quarter first_y last_y '
          'clip1 clip2 floor1 floor2 field_p75_dn1 field_p75_dn2 lit_frac1 lit_frac2 '
          'lateral_bad_rows1 lateral_bad_rows2 uncovered_rows min_pair_score '
          'min_left_guard_score min_right_guard_score worst_y worst_window_x0 status').split()
TRAIN_FIELDS = ('frame full_g1_dn left_g1_dn right_g1_dn r43_pairs margin_cells '
                'pairs_after_margin max_clearance_cells').split()
FIELDS = ('state status state_field_status y0 y1 x0 x1 guard field_us primary_status '
          'cal_500_status qualified_us primary_clip_n primary_floor_n min_pair_score '
          'min_left_guard_score min_right_guard_score min_release_quarter_lit_frac '
          'lateral_bad_rows uncovered_rows').split()


def inventory(frames, scenes):
    groups = {}
    for path in sorted(frames.iterdir()):
        if not path.name.startswith('cal_') or path.suffix.lower() not in ('.dng', '.partial'):
            continue
        m = CAL.fullmatch(path.name)
        if not m or m[1] not in scenes or path.is_symlink() or not path.is_file():
            raise ValueError(f'invalid or unfinished CAL: {path.name}')
        groups.setdefault((m[1], int(m[2])), {})[int(m[3])] = path
    return groups


def capture(path, us, seen, guard):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'missing or invalid DNG: {path.name}')
    try:
        raw, black, white = read_native(path, us)  # A001 / 5.56 mm / ISO 6400 / native GBRG
    except ValueError as exc:
        raise ValueError(f'{path.name}: {exc}') from None
    patch = raw[2*(Y0-guard):2*(Y1+guard), 2*(X0-guard):2*(X1+guard)]
    # Same identity region regardless of bracket/guard. Copies with edited
    # headers or a reused native strip do not provide an independent release.
    key = blake2b(raw[2*Y0:2*Y1:2, 2*X0:2*X1:2].tobytes(), digest_size=16).digest()
    if key in seen:
        raise ValueError(f'{path.name}: duplicate native G1 strip')
    seen.add(key)
    return (patch[::2, ::2].astype(float) - black,
            np.count_nonzero(patch >= white), np.count_nonzero(patch == 0))


def qualify(scene, us, pair, seen):
    if set(pair) != {1, 2}:
        return [dict(kind='cal', scene=scene, exposure_us=us, y0=Y0, y1=Y1, x0=X0, x1=X1,
                     guard=GUARD, status='INCOMPLETE_CAL' if pair else 'MISSING_CAL')]
    caps = [capture(pair[i], us, seen, GUARD) for i in (1, 2)]
    base = dict(kind='cal', scene=scene, exposure_us=us, y0=Y0, y1=Y1, x0=X0, x1=X1,
                guard=GUARD, clip1=caps[0][1], clip2=caps[1][1], floor1=caps[0][2], floor2=caps[1][2])
    if base['floor1'] or base['floor2']:
        return [dict(base, status='FAIL_FLOOR')]
    if base['clip1'] or base['clip2']:
        return [dict(base, status='CLIPPED')]

    # Only the small guarded strip is filtered. R43 levels() checks every
    # native row and every contiguous width-9 horizontal median, >=20 DN,
    # field, same-row and same-column local references and lateral intrusion.
    rel = [levels(g) for g, _, _ in caps]
    scores = np.stack([s for s, _, _ in rel])
    lateral = np.stack([bad for _, bad, _ in rel])
    base.update(field_p75_dn1=rel[0][2], field_p75_dn2=rel[1][2])
    whole = scores.min(axis=2)  # take a complete row from ONE shutter
    support = whole.max(axis=0)
    n = GUARD-WIDTH+1  # windows wholly within each horizontal guard
    left = scores[:, :, :n].min(axis=2).max(axis=0)
    right = scores[:, :, -n:].min(axis=2).max(axis=0)
    rows = []
    for quarter, yy in enumerate(np.array_split(np.arange(BOTTOM-TOP), 4), 1):
        good = (whole[:, yy] >= 1).mean(axis=1)
        bad = lateral[:, yy].sum(axis=1)
        missing = np.count_nonzero(support[yy] < 1)
        y = yy[support[yy].argmin()]
        x = scores[whole[:, y].argmax(), y].argmin()
        rows.append(dict(base, quarter=quarter, first_y=TOP+yy[0], last_y=TOP+yy[-1],
                         lit_frac1=good[0], lit_frac2=good[1], lateral_bad_rows1=bad[0],
                         lateral_bad_rows2=bad[1], uncovered_rows=missing, min_pair_score=support[y],
                         min_left_guard_score=left[yy].min(), min_right_guard_score=right[yy].min(),
                         worst_y=TOP+y, worst_window_x0=LEFT+x,
                         status='PASS' if not missing and not bad.any() and min(good) >= .70 else 'FAIL_FIELD'))
    return rows


def cal_rows(frames, scenes, seen, field_us):
    if field_us not in (1250, 4000):
        raise ValueError('field_us must be 1250 or 4000')
    groups = inventory(frames, scenes)
    rows = []
    for scene in scenes:
        primary = qualify(scene, field_us, groups.get((scene, field_us), {}), seen)
        rows.extend(primary)
        # The repeat 4 ms protocol assesses ONLY its own predeclared pairs.
        if field_us == 1250 and (scene, 500) in groups:
            shorter = qualify(scene, 500, groups[scene, 500], seen)
            rows.extend(shorter)
            if primary[0]['status'] == 'CLIPPED' and all(r['status'] == 'PASS' for r in shorter):
                primary[0]['status'] = 'CLIPPED_REPLACED_BY_500'
    return rows


def run(frames, field_us=1250):
    """All fixed R46 CAL quarters or explicit rail failures; no timing data read."""
    return cal_rows(Path(frames), SCENES, set(), field_us)


def receipts(rows, field_us=1250):
    """Summarize native diagnostics for timing.py; never emit a partial bracket PASS."""
    out = []
    for scene in SCENES:
        local = [r for r in rows if r['scene'] == scene]
        primary = [r for r in local if r['exposure_us'] == field_us]
        shorter = [r for r in local if r['exposure_us'] == 500]

        def status(group):
            return next((r['status'] for r in group if r['status'] != 'PASS'), 'PASS' if group else 'ABSENT')

        p, s = status(primary), status(shorter)
        ok = p in ACCEPTED and s in ('ABSENT', 'PASS')
        state_status = 'PASS' if ok else f'{p}_{field_us}' if p not in ACCEPTED else f'{s}_500'
        effective = shorter if p == 'CLIPPED_REPLACED_BY_500' else primary
        row = dict(state=scene, state_field_status=state_status, status=state_status,
                   y0=Y0, y1=Y1, x0=X0, x1=X1, guard=GUARD, field_us=field_us, primary_status=p,
                   cal_500_status=s if field_us == 1250 else 'NOT_USED')
        if primary and 'clip1' in primary[0]:
            row.update(primary_clip_n=primary[0]['clip1']+primary[0]['clip2'],
                       primary_floor_n=primary[0]['floor1']+primary[0]['floor2'])
        if ok:
            row['qualified_us'] = effective[0]['exposure_us']
        if effective and 'quarter' in effective[0]:
            for k in ('min_pair_score', 'min_left_guard_score', 'min_right_guard_score'):
                row[k] = min(r[k] for r in effective)
            row.update(min_release_quarter_lit_frac=min(min(r['lit_frac1'], r['lit_frac2']) for r in effective),
                       lateral_bad_rows=sum(r['lateral_bad_rows1']+r['lateral_bad_rows2'] for r in effective),
                       uncovered_rows=sum(r['uncovered_rows'] for r in effective))
        out.append(row)
    if any(r['status'] != 'PASS' for r in out):
        for r in out:
            if r['status'] == 'PASS':
                r['status'] = 'BLOCKED_OTHER_CAL'
    return out


def require_geometry(frames, field_us=1250):
    """For timing callers: all three independent R46 CALs must pass together."""
    rows = receipts(run(frames, field_us), field_us)
    bad = [f"{r['state']}: {r['state_field_status']}" for r in rows if r['state_field_status'] != 'PASS']
    if bad:
        raise ValueError('long-strip geometry blocked: ' + '; '.join(bad))
    return rows


def short_strip(path, us, seen):
    """Per-release G1 + QC. CAL does not establish short-exposure signal."""
    g, clip, floor = capture(path, us, seen, 0)
    left, right = np.hsplit(g, [g.shape[1]//2])
    means = g.mean(), left.mean(), right.mean()
    status = 'FAIL_FLOOR' if floor else 'CLIPPED' if clip else 'BELOW_20DN' if min(means) < 20 else 'PASS'
    return g, dict(clip1=clip, floor1=floor, full_g1_dn=means[0], left_g1_dn=means[1],
                   right_g1_dn=means[2], status=status)


def training(frames):
    from direct_camera_r43_20261121.timing import runs, spacing

    seen = set()
    rows = cal_rows(frames, TRAINING, seen, 1250)
    if any(r['status'] not in ACCEPTED for r in rows):
        return rows
    for token, us in [('200', 200), ('312', 312.5), ('500', 500)]:
        for i in range(1, 6):
            path = frames / f'day_onLow_{token}__{i}.dng'
            g, qc = short_strip(path, us, seen)
            row = dict(kind='training_short', scene='onLow', frame=i, exposure_us=us,
                       y0=Y0, y1=Y1, x0=X0, x1=X1, guard=0, margin_cells=MARGIN, **qc)
            if qc['status'] == 'PASS':
                accepted, gaps, _ = spacing(g)  # same-frame, full and both halves
                qualified = set(accepted)
                all_runs = [(a, b) for a, b, _ in runs(g)]
                # Do not connect across a rejected run, even if both farther
                # runs pass and the intermediate run is absent from accepted.
                clearance = [min(a[0], len(g)-1-b[1]) for a, b in zip(all_runs, all_runs[1:])
                             if a in qualified and b in qualified]
                if len(clearance) != len(gaps):
                    raise ValueError(f'{path.name}: R43 adjacent-pair inventory mismatch')
                row.update(r43_pairs=len(gaps), pairs_after_margin=sum(v >= MARGIN for v in clearance),
                           max_clearance_cells=max(clearance, default=None))
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--field-us', type=int, choices=(1250, 4000), default=1250,
                    help='fixed primary CAL shutter for the entire R46 bracket (default 1250)')
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--r45-training', action='store_true', help='replay the design check on frozen R45 only')
    modes.add_argument('--quarters', action='store_true', help='verbose diagnostics for each R46 CAL pair')
    args = ap.parse_args()
    if args.r45_training and args.field_us != 1250:
        ap.error('R45 training uses its frozen 1250 us CALs only')
    try:
        if args.r45_training:
            rows, fields = training(args.frames), QUARTER_FIELDS + TRAIN_FIELDS
        elif args.quarters:
            rows, fields = run(args.frames, args.field_us), QUARTER_FIELDS
        else:
            rows, fields = receipts(run(args.frames, args.field_us), args.field_us), FIELDS
    except (OSError, ValueError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    writer = csv.DictWriter(sys.stdout, fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.8g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})
    if any(r['status'] not in ACCEPTED for r in rows):
        return 1
    if args.r45_training and not any(sum(r.get('pairs_after_margin', 0) > 0 for r in rows if r['exposure_us'] == us) >= 2
                                     for us in (312.5, 500)):
        ap.exit(1, 'FAIL: fewer than two R45 ON releases with a complete interior pair on one shutter\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
