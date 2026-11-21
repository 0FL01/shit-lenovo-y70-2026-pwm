#!/usr/bin/env python3
"""R45 exploratory OFF/200 only: python3 -B spatial.py FRAMES > spatial.csv

Use the original two OFF/1250 CALs and five OFF/200 releases. The fixed G1
ROI anchors the event; the zone estimates are not replacements for its
metrics. Wide-pair centers are exploratory even when CAL passes: the left
zone is below the short-exposure signal gate. Coordinates are native sensor
pixels (half-open limits); a row offset is not panel timing or frequency.
"""

import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r33_20261120.analyze import row_notch
from direct_camera_r43_20261121.geometry import ROI, GUARD, levels, read_native


Y0, Y1, X0, X1 = ROI  # Bayer cells
ROWS = 2 * np.arange(Y0, Y1)
PAIRS = {'wide': (500, 850), 'both_ge20dn': (725, 850)}  # Bayer x, selected by CAL/signal only
HALF_WIDTH = 16  # Bayer cells; 64 native columns in a zone, excluding its guard


def load(path, us, seen):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'missing or invalid original: {path.name}')
    raw, black, white = read_native(path, us)
    patch = raw[2*(Y0-GUARD):2*(Y1+GUARD), 2*(X0-GUARD):2*(X1+GUARD)]
    digest = blake2b(patch.tobytes(), digest_size=16).digest()
    if digest in seen:
        raise ValueError(f'duplicate native RAW patch: {path.name}')
    seen.add(digest)
    return raw, black, white


def zone(raw, black, white, x, guard):
    x0, x1 = x-HALF_WIDTH-guard, x+HALF_WIDTH+guard
    patch = raw[2*(Y0-guard):2*(Y1+guard), 2*x0:2*x1]
    if np.any((patch == 0) | (patch >= white)):
        raise ValueError(f'native RAW rail in zone x={2*x}, guard={2*guard}')
    return patch[::2, ::2].astype(float) - black


def qualify(cals, x):
    # R43/R44 CAL: each candidate row must be lit at once across the whole
    # guarded zone in >=1 CAL, with independent coverage in every quarter.
    results = [levels(zone(*cal, x, GUARD)) for cal in cals]
    whole = np.stack([score.min(axis=1) for score, _, _ in results])
    support = whole.max(axis=0)
    uncovered = int(np.count_nonzero(support < 1))
    lateral = sum(int(bad.sum()) for _, bad, _ in results)
    min_lit = min(q.mean(axis=1).min() for q in np.array_split(whole >= 1, 4, axis=1))
    if uncovered or lateral or min_lit < .70:
        raise ValueError(f'CAL field failed at x={2*x}: {uncovered=}, {lateral=}, {min_lit=}')
    return dict(cal='PASS', cal_uncovered_rows=uncovered, cal_lateral_bad_rows=lateral,
                cal_min_quarter_lit_frac=min_lit, cal_min_pair_score=support.min(),
                cal1_p75_dn=results[0][2], cal2_p75_dn=results[1][2])


def estimate(signal, anchor):
    profile = np.convolve(signal.mean(axis=1), np.ones(3)/3, 'valid')
    rows = ROWS[1:-1]
    d = np.abs(rows-anchor)
    if not rows[0] <= anchor-104 or not anchor+104 <= rows[-1]:
        raise ValueError('baseline event lacks complete shoulders')
    plateau = np.median(profile[(52 <= d) & (d <= 104)])
    lo = int(np.argmin(np.where(d <= 30, profile, np.inf)))
    bottom = profile[lo]
    if not plateau > max(0, bottom):
        raise ValueError('no local dip')
    half = (plateau+bottom)/2
    above = (d <= 52) & (profile >= half)
    left = np.flatnonzero(above & (rows < rows[lo]))
    right = np.flatnonzero(above & (rows > rows[lo]))
    if not left.size or not right.size:
        raise ValueError('missing half-depth crossing')
    l, r = left[-1], right[0]
    yl = np.interp(half, profile[[l+1, l]], rows[[l+1, l]])
    yr = np.interp(half, profile[r-1:r+1], rows[r-1:r+1])
    if not yl < anchor < yr:
        raise ValueError('zone dip does not contain the same baseline event')
    mean = signal.mean()
    return dict(g1_mean_dn=mean, g1_mean_ge20dn=int(mean >= 20),
                g1_plateau_dn=plateau, g1_min_dn=bottom,
                half_lo_raw_y=yl, half_hi_raw_y=yr,
                center_raw_y=(yl+yr)/2, fwhm_raw_rows=yr-yl)


def run(frames):
    seen = set()
    cals = [load(frames/f'cal_offLow_1250__{i}.dng', 1250, seen) for i in (1, 2)]
    zones = sorted({x for pair in PAIRS.values() for x in pair})
    cal = {x: qualify(cals, x) for x in zones}
    out = []
    for i in range(1, 6):
        path = frames/f'day_offLow_200__{i}.dng'
        try:
            raw, black, white = load(path, 200, seen)
            base = raw[2*Y0:2*Y1:2, 2*X0:2*X1:2]
            if np.any((base == 0) | (base >= white)) or base.mean()-black < 20:
                raise ValueError('baseline G1 signal gate failed')
            anchor = row_notch(base.astype(float)-black, Y0, True)['notch_center_raw_y']
            if anchor is None:
                raise ValueError('no baseline event')
            metrics = {x: estimate(zone(raw, black, white, x, 0), anchor) for x in zones}
            for pair, (xl, xr) in PAIRS.items():
                left, right = metrics[xl], metrics[xr]
                if pair == 'both_ge20dn' and not (left['g1_mean_ge20dn'] and right['g1_mean_ge20dn']):
                    raise ValueError('short-exposure signal gate failed for both_ge20dn pair')
                row = dict(frame_n=i, exposure_us=200, pair=pair, baseline_anchor_raw_y=anchor,
                           raw_y0=2*Y0, raw_y1=2*Y1, cal_guard_raw_px=2*GUARD,
                           dx_raw_cols=2*(xr-xl),
                           right_minus_left_center_raw_rows=right['center_raw_y']-left['center_raw_y'],
                           overlap_raw_rows=min(left['half_hi_raw_y'], right['half_hi_raw_y'])
                           - max(left['half_lo_raw_y'], right['half_lo_raw_y']))
                for side, x in (('left', xl), ('right', xr)):
                    data = dict(raw_x0=2*(x-HALF_WIDTH), raw_x1=2*(x+HALF_WIDTH),
                                **metrics[x], **cal[x])
                    row.update({f'{side}_{k}': v for k, v in data.items()})
                out.append(row)
        except ValueError as exc:
            raise ValueError(f'{path.name}: {exc}') from None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    try:
        rows = run(args.frames)
    except (ValueError, OSError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    writer = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: f'{v:.6f}' if isinstance(v, (float, np.floating)) else v
                      for k, v in row.items()} for row in rows)


if __name__ == '__main__':
    main()
