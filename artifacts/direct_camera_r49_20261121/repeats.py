#!/usr/bin/env python3
"""R49: python3 -B repeats.py FRAMES > repeats.csv  (use --rows for profiles).

Four separate 4-ms exposures per leg; compare the same native sensor rows. G1
means above tagged black, followed by a centered 3-cell boxcar (valid only).
No shift, fit, gain normalization, flat, or substitution from another shutter.
Span is max minus min over the four releases at each row; percent uses that
row's maximum. Quantiles and fractions describe rows, not independent trials.

Even/odd alternate G1 columns. The inter-frame span of their half-difference
estimates the uncorrelated component of the full-width span; it is not a noise
bound. Signed pairwise correlations remove each pair's constant brightness shift.
An off-panel strip on the same rows checks for a common sensor-row contribution.
Edges check apparent image motion only; a uniform field cannot prove a fixed
viewing angle. The DAY guard is a diagnostic on these data, not a CAL. These
exposure-integrated changes establish neither instantaneous PWM depth nor Hz.
"""
import argparse
import csv
from hashlib import blake2b
from itertools import combinations
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.geometry import read_native
from direct_camera_r43_20261121.geometry import BOTTOM, GUARD, LEFT, RIGHT, TOP, X0, X1, Y0, Y1
from direct_camera_r47_20261121.field import releases
from direct_camera_r48_20261121.field import qualify
from direct_camera_r48_20261121.measure import native_orientation


def profile(g):
    return np.convolve(g.mean(axis=1), np.ones(3)/3, 'valid')


def edge(strip, start):
    """First center past local half contrast; require a single crossing, no fit."""
    p = np.convolve(strip.mean(axis=0), np.ones(9)/9, 'valid')
    outside, inside = np.median(p[:15]), np.median(p[-15:])
    if abs(inside-outside) < 5:  # edge unresolved; don't substitute a coordinate
        return None
    lit = (p-outside)/(inside-outside) >= .5
    steps = np.flatnonzero(lit[1:] != lit[:-1])
    if len(steps) == 1 and not lit[0] and lit[-1]:
        return start + 4 + 1 + int(steps[0])
    return None


def capture(path, seen):
    raw, black, white = read_native(path, 4000)
    patch = raw[2*TOP:2*BOTTOM, 2*LEFT:2*RIGHT]
    digest = blake2b(patch.tobytes(), digest_size=16).digest()
    if digest in seen:
        raise ValueError(f'{path.name}: duplicate guarded RAW samples')
    seen.add(digest)
    guard = (patch[::2, ::2].astype(float)-black, (patch >= white).sum(), (patch == 0).sum())
    roi = raw[2*Y0:2*Y1:2, 2*X0:2*X1:2]
    if ((roi == 0) | (roi >= white)).any() or roi.mean()-black < 20:
        raise ValueError(f'{path.name}: railed or below-20-DN G1 ROI')
    g = roi.astype(float)-black
    # R34's off-screen x=245:400 witness, narrowed to the same 45-column width.
    outside = raw[2*Y0:2*Y1:2, 600:690:2]
    if ((outside == 0) | (outside >= white)).any():
        raise ValueError(f'{path.name}: railed off-screen witness')
    profs = [profile(s) for s in (g, g[:, ::2], g[:, 1::2], outside.astype(float)-black)]
    # Independent of the science profiles. Bracket R34's left, right and top
    # illuminated boundaries (~446/1117/558 cells), not a trough or a cable.
    plane = raw[::2, ::2]
    coords = [edge(plane[y-10:y+11, 380:525], 380) for y in (785, 1095)]
    coords.append(edge(plane[775:796, 1050:1190], 1050))
    # R34 top-edge witness at x=640 and the ROI center. Preserve NA where
    # multiple transitions preclude identifying a single illuminated edge.
    coords.extend(edge(plane[480:620, x-10:x+11].T, 480) for x in (640, 776))
    return guard, profs, coords


def sequence(values):
    return ';'.join('NA' if v is None else str(v) for v in values)


def analyze(directory, leg, seen):
    phase = f'day_{leg}_4000'
    files = releases(directory, phase)
    if set(files) != {1, 2, 3, 4}:
        raise ValueError(f'{phase}: need exactly four original releases, __1..4')
    caps, profiles, coords = zip(*(capture(files[i], seen) for i in range(1, 5)))
    field = qualify(caps)  # R48 guarded illumination test on the DAY originals
    full, even, odd, outside = np.asarray(profiles).transpose(1, 0, 2)
    means = [g[GUARD:-GUARD, GUARD:-GUARD].mean() for g, _, _ in caps]
    out = dict(phase=phase, exposure_us=4000, orientation=6, n_releases=4, n_rows=full.shape[1],
               roi_g1_mean_dn=np.mean(means), min_frame_mean_dn=min(means), max_frame_mean_dn=max(means),
               min_row_max_dn=full.max(axis=0).min(), day_guard_status=next(
                   (q['status'] for q in field if q['status'] != 'PASS'), 'PASS'),
               guard_clip_n=sum(c for _, c, _ in caps), guard_floor_n=sum(f for _, _, f in caps),
               guard_uncovered_rows=None, guard_lateral_bad_row_releases=None, guard_min_lit_frac=None)
    if all('quarter' in q for q in field):
        out.update(guard_uncovered_rows=sum(q['uncovered_rows'] for q in field),
                   guard_lateral_bad_row_releases=sum(q[f'lateral_bad_rows{i}'] for q in field for i in range(1, 5)),
                   guard_min_lit_frac=min(q[f'lit_frac{i}'] for q in field for i in range(1, 5)))

    details = [dict(phase=phase, raw_y=2*y) for y in range(Y0+1, Y1-1)]
    for label, p in [('full', full), ('even', even), ('odd', odd)]:
        if np.any(p.max(axis=0) <= 0):
            raise ValueError(f'{phase}: nonpositive same-row denominator ({label})')
        span = np.ptp(p, axis=0)
        pct = 100*span/p.max(axis=0)
        out.update({label+'_p50_dn': np.median(span), label+'_p95_dn': np.percentile(span, 95),
                    label+'_p50_pct': np.median(pct), label+'_p95_pct': np.percentile(pct, 95),
                    label+'_frac_gt5pct': np.mean(pct > 5)})
        for j, row in enumerate(details):
            if label == 'full':
                row.update({f'g1_dn{i+1}': v for i, v in enumerate(p[:, j])})
            row.update({label+'_span_dn': span[j], label+'_span_pct': pct[j]})

    residual = np.ptp((even-odd)/2, axis=0)
    # Signed inter-release differences: static gradients cancel; correlation is
    # across rows for each pair separately. Include all six, report the weakest.
    rs = [np.corrcoef(even[i]-even[j], odd[i]-odd[j])[0, 1] for i, j in combinations(range(4), 2)]
    out.update(split_pair_min_r=min(rs) if np.isfinite(rs).all() else None,
               split_halfdiff_span_p95_dn=np.percentile(residual, 95), offscreen_mean_dn=outside.mean(),
               offscreen_span_p95_dn=np.percentile(np.ptp(outside, axis=0), 95))
    for key, values in zip(('left_x_at_y785', 'left_x_at_y1095', 'right_x_at_y785',
                            'top_y_at_x640', 'top_y_at_x776'), zip(*coords)):
        out[key+'_cells'] = sequence(values)
    # Apparent in-plane orientation of the left edge, not viewing angle to the OLED.
    slopes = [np.degrees(np.arctan((b-a)/(1095-785))) for a, b, *_ in coords if a is not None and b is not None]
    out['left_edge_angle_span_deg'] = np.ptp(slopes) if len(slopes) == 4 else None
    return out, details


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--rows', action='store_true', help='emit all same-row profiles instead of the summary')
    args = ap.parse_args()
    seen, rows = set(), []
    try:
        with native_orientation(6):
            for leg in 'AB':
                summary, details = analyze(args.frames, leg, seen)
                rows.extend(details if args.rows else [summary])
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
