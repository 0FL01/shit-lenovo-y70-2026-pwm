#!/usr/bin/env python3
"""R43: python3 -B geometry.py FRAMES > geometry.csv

Qualify the *illuminated field* at the fixed camera coordinates, not just the
decoded 720x1584 raster or the visible SurfaceView. Those and the target PNG
are independent evidence. A uniform field has no fiducial: PASS does not
identify video pixels, measure exact registration, verify EOTF or measure PWM.

Require two distinct cal_SCENE_{1250,500}__N.dng releases per bracket used,
including sdr, hdr and sdrRet. Keep any clipped 1250 us pair in the report;
only a passing 500 us pair of the same scene can supersede it. Check the fixed
guard, not the entire screen: bars outside it are immaterial for this test.
"""

import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.geometry import read_native
from direct_camera_r42_20261121.measure import ROI


Y0, Y1, X0, X1 = ROI  # half-open native Bayer cells, no EXIF rotation
GUARD = 20
TOP, BOTTOM, LEFT, RIGHT = Y0-GUARD, Y1+GUARD, X0-GUARD, X1+GUARD
WIDTH = 9  # horizontal median only; small/low-contrast blemishes are unresolved
CAL = re.compile(r'cal_((?:sdr|hdr)[A-Za-z0-9]*)_(1250|500)__([12])\.dng')


def inventory(frames):
    groups = {}
    for p in sorted(frames.iterdir()):
        if not p.name.startswith('cal_') or p.suffix.lower() not in ('.dng', '.partial'):
            continue
        m = CAL.fullmatch(p.name)
        if not m or not p.is_file() or p.is_symlink():
            raise ValueError(f'invalid or unfinished CAL: {p.name}')
        groups.setdefault((m[1], int(m[2])), {})[int(m[3])] = p
    for (scene, us), pair in groups.items():
        if set(pair) != {1, 2}:
            raise ValueError(f'{scene}/{us}: expected two CALs (__1 and __2)')
    missing = {'sdr', 'hdr', 'sdrRet'} - {scene for scene, _ in groups}
    if missing:
        raise ValueError('missing required CAL pairs: ' + ', '.join(sorted(missing)))
    return groups


def capture(path, us, seen):
    raw, black, white = read_native(path, us)  # also verifies A001, lens, ISO, GBRG and scale
    patch = raw[2*TOP:2*BOTTOM, 2*LEFT:2*RIGHT]
    digest = blake2b(patch.tobytes(), digest_size=16).digest()
    if digest in seen:
        raise ValueError(f'{path.stem}: duplicate native CAL patch')
    seen.add(digest)
    return (patch[::2, ::2].astype(float) - black,
            np.count_nonzero(patch >= white), np.count_nonzero(patch == 0))


def levels(g1):
    # Sliding windows start at LEFT and end at RIGHT; no vertical smoothing of
    # observations, padding, skipped end rows or quarter averaging for a PASS.
    a = np.median(sliding_window_view(g1, WIDTH, axis=1), axis=-1)
    field = np.percentile(a, 75)
    row = np.percentile(a, 75, axis=1, keepdims=True)
    # Local same-column plateau accommodates slow spatial shading. Neighbours
    # set the reference only: never use one to fill an unilluminated row.
    near = np.array([np.percentile(a[max(0, y-40):y+41], 75, axis=0) for y in range(len(a))])
    limit = np.maximum(np.maximum(20., .40*field), np.maximum(.65*row, .70*near))
    score = a / limit  # >=1: absolute DN, broad-field, lateral and local vertical support
    # A partial-width occlusion on an otherwise lit row must not be rescued by
    # another release. Do not apply this lateral test on noise in a deep trough.
    lit = row >= np.maximum(max(20., .40*field), .70*np.percentile(near, 75, axis=1, keepdims=True))
    lateral_fail = (lit & (a < np.maximum(20., .65*row))).any(axis=1)
    return score, lateral_fail, field


def qualify(scene, us, pair, seen):
    caps = [capture(pair[i], us, seen) for i in (1, 2)]
    base = dict(scene=scene, exposure_us=us, y0=Y0, y1=Y1, x0=X0, x1=X1, guard=GUARD,
                clip1=caps[0][1], clip2=caps[1][1], floor1=caps[0][2], floor2=caps[1][2])
    if base['floor1'] or base['floor2'] or base['clip1'] or base['clip2']:
        status = 'FAIL_FLOOR' if base['floor1'] or base['floor2'] else 'CLIPPED'
        return [dict(base, status=status)]

    releases = [levels(g) for g, _, _ in caps]
    scores = np.stack([s for s, _, _ in releases])
    lateral_fail = np.stack([f for _, f, _ in releases])
    base.update(field_p75_dn1=releases[0][2], field_p75_dn2=releases[1][2])
    # First take the worst horizontal window of EACH row in EACH CAL. Only
    # then take the better release: an entire row, both corners included, must
    # have been illuminated at once. Independent shutters need not share phase.
    whole_row = scores.min(axis=2)
    support = whole_row.max(axis=0)
    rows = []
    for quarter, yy in enumerate(np.array_split(np.arange(BOTTOM-TOP), 4), 1):
        y = yy[np.argmin(support[yy])]
        release = np.argmax(whole_row[:, y])
        x = np.argmin(scores[release, y])
        good = (whole_row[:, yy] >= 1).mean(axis=1)
        lateral = lateral_fail[:, yy].sum(axis=1)
        uncovered = np.count_nonzero(support[yy] < 1)
        # No persistent dark row; no one-CAL lateral intrusion on a lit row;
        # independent broad support in every quarter (not one good CAL + one dark).
        ok = not uncovered and not lateral.any() and min(good) >= .70
        rows.append(dict(base, quarter=quarter, first_y=TOP+yy[0], last_y=TOP+yy[-1],
                         lit_frac1=good[0], lit_frac2=good[1], lateral_bad_rows1=lateral[0],
                         lateral_bad_rows2=lateral[1], uncovered_rows=uncovered,
                         min_pair_score=support[y], worst_y=TOP+y, worst_window_x0=LEFT+x,
                         status='PASS' if ok else 'FAIL_FIELD'))
    return rows


def run(frames):
    groups = inventory(frames)
    seen, pairs = set(), {}
    for (scene, us), pair in groups.items():
        try:
            pairs[scene, us] = qualify(scene, us, pair, seen)
        except ValueError as exc:
            raise ValueError(f'{scene}/{us}: {exc}') from None
    for (scene, us), rows in pairs.items():
        shorter = pairs.get((scene, 500))
        if (us == 1250 and rows[0]['status'] == 'CLIPPED' and shorter and
                all(r['status'] == 'PASS' for r in shorter)):
            rows[0]['status'] = 'CLIPPED_REPLACED_BY_500'
    return [row for rows in pairs.values() for row in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    try:
        rows = run(args.frames)
    except (OSError, ValueError) as exc:
        ap.exit(1, 'FAIL: ' + (exc.strerror if isinstance(exc, OSError) else str(exc)) + '\n')
    fields = ('scene exposure_us y0 y1 x0 x1 guard clip1 clip2 floor1 floor2 quarter first_y last_y '
              'field_p75_dn1 field_p75_dn2 lit_frac1 lit_frac2 lateral_bad_rows1 lateral_bad_rows2 '
              'uncovered_rows min_pair_score worst_y worst_window_x0 status').split()
    out = csv.DictWriter(sys.stdout, fields, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.7g') if isinstance(v, float) else v for k, v in row.items()})
    return int(any(r['status'] not in ('PASS', 'CLIPPED_REPLACED_BY_500') for r in rows))


if __name__ == '__main__':
    sys.exit(main())
