#!/usr/bin/env python3
"""Secondary geometry only: python3 -B extended.py FRAMES > extended.csv

Extend the original native G1 strip vertically by multiples of ten Bayer
cells, keeping its columns and 20-cell perimeter guard. Use only the two
on120A and two on144B 4 ms CAL releases for selection. Visit the grid by
decreasing length, decreasing smaller extension, then increasing y0. The
first exact R43 pass on both pairs freezes the rectangle. Only then open
the two on120C CALs and test that rectangle once. Never read DAY or timing
data. C is a held-out calibration in the same bracket, not a physical replica.

All bounds are half-open Bayer cells. status=PASS permits secondary timing
only for an actual extension with all three pairs qualified; SAME is not a
new observation. This procedure does not change the primary strip result.
"""

import argparse
import csv
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import GUARD, WIDTH, levels, read_native
from direct_camera_r46_20261121.strip import ROI, SCENES


Y0, Y1, X0, X1 = ROI
H, STEP, US = 1536, 10, 4000


@dataclass
class Release:
    start: int  # first stored guarded Bayer row
    g: np.ndarray
    clip: np.ndarray
    floor: np.ndarray

    def interval(self, lo, hi):
        s = slice(lo-GUARD-self.start, hi+GUARD-self.start)
        return self.g[s], int(self.clip[s].sum()), int(self.floor[s].sum())


def load(frames, scene, seen, start=0, stop=H):
    caps = []
    for n in (1, 2):
        p = frames/f'cal_{scene}_{US}__{n}.dng'
        if p.is_symlink() or not p.is_file():
            raise ValueError(f'missing or invalid CAL: {p.name}')
        raw, black, white = read_native(p, US)
        key = blake2b(raw[2*Y0:2*Y1:2, 2*X0:2*X1:2].tobytes(), digest_size=16).digest()
        if key in seen:
            raise ValueError(f'{p.name}: duplicate native G1 strip')
        seen.add(key)
        patch = raw[2*start:2*stop, 2*(X0-GUARD):2*(X1+GUARD)]
        # Any CFA site on a storage rail anywhere inside the guarded bounds.
        clip = (patch >= white).reshape(stop-start, -1).sum(axis=1)
        floor = (patch == 0).reshape(stop-start, -1).sum(axis=1)
        caps.append(Release(start, patch[::2, ::2].astype(float)-black, clip, floor))
    return caps


def impossible(pair):
    """Necessary rejections only, unaffected by changing endpoints or quarters."""
    possible = []
    for cap in pair:
        a = np.median(sliding_window_view(cap.g, WIDTH, axis=1), axis=-1)
        row = np.percentile(a, 75, axis=1)
        possible.append(a.min(axis=1) >= np.maximum(20., .65*row))
    # R43 requires a whole lit row in one release and no rails in either.
    return (~np.logical_or(*possible) | (pair[0].clip+pair[0].floor+pair[1].clip+pair[1].floor > 0))


def exact(pair, lo, hi):
    caps = [cap.interval(lo, hi) for cap in pair]
    r = dict(clip1=caps[0][1], clip2=caps[1][1], floor1=caps[0][2], floor2=caps[1][2])
    if r['floor1'] or r['floor2'] or r['clip1'] or r['clip2']:
        return dict(r, state_field_status='FAIL_FLOOR' if r['floor1'] or r['floor2'] else 'CLIPPED')

    # Recompute field P75 and endpoint-truncated +/-40-cell column references
    # on THIS candidate (full-column scores can change when the ROI shrinks).
    rel = [levels(g) for g, _, _ in caps]
    scores = np.stack([v[0] for v in rel])
    whole = scores.min(axis=2)
    support = whole.max(axis=0)  # no opposite-half or inter-release mosaics
    y = int(support.argmin())
    winner = whole[:, y].argmax()
    q = np.stack([part.mean(axis=1) for part in np.array_split(whole >= 1, 4, axis=1)])
    lateral = [int(v[1].sum()) for v in rel]
    n = GUARD-WIDTH+1
    ok = support[y] >= 1 and not any(lateral) and q.min() >= .70
    return dict(r, state_field_status='PASS' if ok else 'FAIL_FIELD',
                min_pair_score=support[y], worst_y=lo-GUARD+y,
                worst_window_x0=X0-GUARD+scores[winner, y].argmin(),
                min_left_guard_score=scores[:, :, :n].min(axis=2).max(axis=0).min(),
                min_right_guard_score=scores[:, :, -n:].min(axis=2).max(axis=0).min(),
                min_release_score1=whole[0].min(), min_release_score2=whole[1].min(),
                field_p75_dn1=rel[0][2], field_p75_dn2=rel[1][2],
                min_quarter_lit_frac1=q[:, 0].min(), min_quarter_lit_frac2=q[:, 1].min(),
                lateral_bad_rows1=lateral[0], lateral_bad_rows2=lateral[1],
                uncovered_rows=np.count_nonzero(support < 1))


def select(pairs):
    bad = np.r_[0, np.cumsum(impossible(pairs[0]) | impossible(pairs[1]))]
    grid = sorted(((lo, hi) for lo in range(Y0, GUARD-1, -STEP)
                   for hi in range(Y1, H-GUARD+1, STEP)),
                  key=lambda v: (v[0]-v[1], -min(Y0-v[0], v[1]-Y1), v[0]))
    for lo, hi in grid:
        if bad[hi+GUARD] != bad[lo-GUARD]:
            continue
        a = exact(pairs[0], lo, hi)
        if a['state_field_status'] == 'PASS':
            b = exact(pairs[1], lo, hi)
            if b['state_field_status'] == 'PASS':
                return lo, hi, a, b
    raise ValueError('no rectangle, including the original, passes both selection pairs; C not tested')


def run(frames):
    seen = set()
    lo, hi, a, b = select([load(frames, scene, seen) for scene in SCENES[:2]])
    # No held-out data accessed before selection; no retry, trimming or fallback.
    c = exact(load(frames, SCENES[2], seen, lo-GUARD, hi+GUARD), lo, hi)
    choice = 'SAME' if (lo, hi) == (Y0, Y1) else 'EXTENDED'
    rows = []
    for scene, metrics in zip(SCENES, (a, b, c)):
        status = ('BLOCKED_HELD_OUT_C' if c['state_field_status'] != 'PASS' else
                  'SAME' if choice == 'SAME' else 'PASS')
        rows.append(dict(state=scene, status=status, y0=lo, y1=hi, x0=X0, x1=X1, guard=GUARD,
                         qualified_us=US if metrics['state_field_status'] == 'PASS' else None, field_us=US,
                         selection='AB_CAL_only_C_holdout', choice=choice,
                         role='held_out_once' if scene == SCENES[2] else 'selection',
                         protocol='secondary_AB_4ms_CAL_grid_C_holdout_same_bracket',
                         original_y0=Y0, original_y1=Y1, original_x0=X0, original_x1=X1,
                         grid_step=STEP, **metrics))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    args = ap.parse_args()
    try:
        rows = run(args.frames)
    except (ValueError, OSError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    wr = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys(), lineterminator='\n')
    wr.writeheader()
    for row in rows:
        wr.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})
    return int(rows[-1]['state_field_status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
