#!/usr/bin/env python3
"""R46: python3 -B width.py FRAMES > width.csv
Control: python3 -B width.py --r45-control R45_FRAMES > r45-width.csv

Independent morphology diagnostic, not the R44/R46 primary depth decision.
Fixed R42 G1 ROI; one row per release (six or eight R46 originals per state/shutter,
five per R45 ON shutter). Above tagged black, no rail, >=20 DN mean in full
ROI and both halves. Gates and definitions fixed before evaluating R46:

* R43 runs() supplies candidates only: at least 3 consecutive valid 3-cell
  means below 0.70 of the local median. Its wing/plateau flags are recorded,
  not used as calibrated light levels. No new search outside these runs.
* For inclusive run [a,b] in native G1 cells, independently measure the
  medians of smoothed cells [a-40,a-21] and [b+21,b+40]. Require both >=20
  DN. Interpolate a linear plateau only BETWEEN the two band midpoints.
* In the run choose the darkest complete 5-cell median of the smoothed full
  profile relative to that plateau; fix its center and floor window for BOTH
  horizontal halves. Floor is signed DN; depth = 100*(1-floor/plateau).
  Each flank minus floor must exceed max(1 DN, 5*1.4826*MAD on either flank,
  3*sqrt(2)*RMS of the interleaved-column noise estimate between the flanks).
  This empirical gate includes column texture; it is not a confidence bound.
* FWHM is the distance between linearly interpolated, observed crossings of
  (1+floor/plateau)/2 on the normalized profile around the same anchor. No
  second >=3-cell half-depth core between flanks. Require width >=12 RAW rows
  and >=6 UNSMOOTHED native cell means below half-depth inside the interval.
* Repeat all gates in both halves. Across the three fits depth spread <=10 pp,
  width and midpoint spreads each <=max(4 RAW rows, 20% of full width). Take
  the qualifying full midpoint nearest the fixed ROI center (upper if tied).
  Other runs/halves do not increase the number of independent releases.

Blank width is unmeasured. These are exposure-integrated image troughs; widths
alone do not identify a physical component. Check fine.csv for carrier ambiguity,
windows.csv for state and CAL for field/light comparability. Converting RAW rows
requires a qualified, applicable same-state scale from timing.py at matched
shutter/geometry. Even then this is NOT native panel off-time or PWM frequency.
"""

import argparse
from collections import Counter
import csv
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.measure import ROI, inputs, read_sites, sample
from direct_camera_r43_20261121.timing import US, runs


SHUTTERS = ('200', '312', '500')
FIELDS = ('state phase frame_n exposure_us mean_dn left_mean_dn right_mean_dn gate '
          'runs_n r43_seed_counts qualified_n rejected status seed_lo_raw_y seed_hi_raw_y '
          'anchor_raw_y flank_lo_dn flank_hi_dn floor_dn plateau_dn noise_gate_dn depth_pct '
          'cross_lo_raw_y cross_hi_raw_y center_raw_y fwhm_raw_rows left_depth_pct right_depth_pct '
          'left_center_raw_y right_center_raw_y left_fwhm_raw_rows right_fwhm_raw_rows').split()


def profile(g):
    """Native cell index i is the center of valid sm[i]; endpoints stay NaN."""
    def smooth(x):
        return np.r_[np.nan, np.convolve(x, np.ones(3)/3, 'valid'), np.nan]

    p = g.mean(1)
    a, b = g[:, ::2], g[:, 1::2]
    noise = (a.mean(1)-b.mean(1)) * np.sqrt(a.shape[1]*b.shape[1])/g.shape[1]
    return p, smooth(p), smooth(noise)


def measure_run(prof, a, b, anchor):
    p, sm, noise = prof
    if a-40 < 1 or b+40 >= len(p)-1:
        return 'incomplete_flanks', {}
    if b-a+1 < 5:
        return 'short_floor_window', {}
    flanks = sm[a-40:a-20], sm[b+21:b+41]
    lo, hi = map(np.median, flanks)
    if min(lo, hi) < 20:
        return 'dim_flank', {}
    # Anchor locations a-30.5, b+30.5. All fitted samples and crossings
    # are strictly inside this observed interval; no clamping or padding.
    x = np.arange(a-30, b+31)
    bg = np.interp(x, [a-30.5, b+30.5], [lo, hi])
    ratio = sm[x]/bg
    if anchor is None:
        floors = np.median(sliding_window_view(sm[a:b+1], 5), axis=1)
        anchor = a+2+int(np.argmin(floors/bg[a+2-x[0]:b-1-x[0]]))
    k = anchor-x[0]
    floor, plateau = np.median(sm[anchor-2:anchor+3]), bg[k]
    gate = max(1., 5*1.4826*max(np.median(abs(f-np.median(f))) for f in flanks),
               3*np.sqrt(2)*np.sqrt(np.mean(noise[a-40:b+41]**2)))
    if min(lo, hi)-floor <= gate:
        return 'weak_against_flanks', {}
    level = (1+floor/plateau)/2
    inside = ratio < level
    if not inside[k]:
        return 'anchor_not_in_core', {}
    changes = np.flatnonzero(np.diff(np.r_[False, inside, False].astype(int))).reshape(-1, 2)
    (l, r), = [(l, r) for l, r in changes if l <= k < r]  # r exclusive
    if l == 0 or r == len(x):
        return 'unbounded_half_depth', {}
    if any(j-i >= 3 for i, j in changes if i != l):
        return 'multiple_half_depth_cores', {}
    xl = np.interp(level, ratio[[l, l-1]], x[[l, l-1]])
    xr = np.interp(level, ratio[r-1:r+1], x[r-1:r+1])
    if xr-xl < 6 or np.count_nonzero((xl < x) & (x < xr) & (p[x] < level*bg)) < 6:
        return 'insufficient_native_width', {}
    low, high = 2*(ROI[0]+xl), 2*(ROI[0]+xr)
    return 'ok', dict(anchor_raw_y=2*(ROI[0]+anchor), flank_lo_dn=lo, flank_hi_dn=hi,
                      floor_dn=floor, plateau_dn=plateau, noise_gate_dn=gate,
                      depth_pct=100*(1-floor/plateau), cross_lo_raw_y=low, cross_hi_raw_y=high,
                      center_raw_y=(low+high)/2, fwhm_raw_rows=high-low)


def check(profiles, a, b):
    status, full = measure_run(profiles[0], a, b, None)
    if status != 'ok':
        return status, {}
    fits = [full]
    anchor = full['anchor_raw_y']//2-ROI[0]
    for side, prof in zip(('left', 'right'), profiles[1:]):
        status, half = measure_run(prof, a, b, anchor)
        if status != 'ok':
            return side+'_'+status, {}
        fits.append(half)
    tolerance = max(4, .20*full['fwhm_raw_rows'])
    for key in ('depth_pct', 'center_raw_y', 'fwhm_raw_rows'):
        if np.ptp([m[key] for m in fits]) > (10 if key == 'depth_pct' else tolerance):
            return 'half_disagreement_'+key, {}
    out = dict(full, seed_lo_raw_y=2*(ROI[0]+a), seed_hi_raw_y=2*(ROI[0]+b))
    for side, values in zip(('left', 'right'), fits[1:]):
        out.update({side+'_'+k: values[k] for k in ('depth_pct', 'center_raw_y', 'fwhm_raw_rows')})
    return 'ok', out


def counts(items):
    return ';'.join(f'{key}:{n}' for key, n in sorted(Counter(items).items()))


def frame(path, us, seen):
    if path.is_symlink():
        raise ValueError(f'{path.name}: expected original DNG')
    m, planes = read_sites(path, us)
    key = blake2b(planes['G1'].tobytes(), digest_size=16).digest()
    if key in seen:
        raise ValueError(f'{path.name}: repeated native G1 samples')
    seen.add(key)
    g, q = sample(planes['G1'], m['black_levels'][0], m['white_level'], False)
    left, right = np.hsplit(g, [g.shape[1]//2])
    row = dict(mean_dn=q['mean_dn'], left_mean_dn=left.mean(), right_mean_dn=right.mean(), gate=q['gate'])
    if q['gate'] != 'ok' or min(left.mean(), right.mean()) < 20:
        return dict(row, status=q['gate'] if q['gate'] != 'ok' else 'half_below_20dn')
    profiles = [profile(h) for h in (g, left, right)]
    seeds = runs(g)
    found, rejected = [], []
    for a, b, _ in seeds:
        status, fit = check(profiles, a, b)
        if status == 'ok':
            found.append(fit)
        else:
            rejected.append(status)
    row.update(runs_n=len(seeds), qualified_n=len(found), rejected=counts(rejected),
               r43_seed_counts=counts(s for _, _, s in seeds))
    if not found:
        return dict(row, status='no_qualified_run' if seeds else 'no_run')
    midpoint = ROI[0]+ROI[1]-1  # midpoint of the first and last physical G1 RAW rows
    chosen = min(found, key=lambda f: (abs(f['center_raw_y']-midpoint), f['center_raw_y']))
    return dict(row, status='ok', **chosen)


def analyze(directory, control, releases=6):
    paths, seen = inputs(directory), set()
    for state in (('onLow',) if control else ('on120A', 'on144B', 'on120C')):
        for token in SHUTTERS:
            phase = f'day_{state}_{token}'
            ns = sorted(n for ph, n in paths if ph == phase)
            expected = 5 if control else releases
            if ns != list(range(1, expected+1)):
                raise ValueError(f'{phase}: expected releases 1..{expected}; got {ns}')
            for n in ns:
                row = frame(paths[phase, n], US[token], seen)
                yield dict(state=state, phase=phase, frame_n=n, exposure_us=US[token], **row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    ap.add_argument('--r45-control', action='store_true', help='use the archived native R45 ON triplet of shutters')
    ap.add_argument('--releases', type=int, choices=(6,8), default=6)
    args = ap.parse_args()
    try:
        rows = list(analyze(args.frames, args.r45_control, args.releases))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
