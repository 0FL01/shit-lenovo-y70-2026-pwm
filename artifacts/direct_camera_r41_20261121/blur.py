#!/usr/bin/env python3
"""R41: estimate the effective phase gradient of a broad notch (µs per RAW row).

Use the complete 24-window daytime matrix, not the pilot, tiles or evening series.
Each same-color short/500 µs pair uses the R35 commuting-box cost on unsmoothed
profiles: short blurred with the long shutter should match long blurred with the
short shutter. The R35 peak/wing detector below is adapted to a single CFA site
so that *rejected* frames and edge candidates are visible. Selection favors
strong, isolated dips with two visible wings. One event per DNG. Smooth-11/31
and wing-10/25 alternatives only flag sensitivity; they never rescue a frame.

The group optimum minimizes median pair loss; pair_median/min/max describe
individual optima on the same µs/RAW-row grid. At least two complete DNGs per
exposure are required; pairs counts evaluated pairs. Pairs reuse frames:
neither the range nor the width of the
loss minimum is a statistical confidence interval. A full calibration of camera
row time, the intrinsic off-time and physical PWM frequency do not follow.
"""

import argparse
from collections import Counter
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r35_20261120.blur import cost  # also uses the original fractional box()
from direct_camera_r41_20261121.measure import ROI, SITES, decode_dng_bytes, extract_metadata, inputs


PRIMARY = {'white': 'G1', 'red': 'R', 'green': 'G1', 'blue': 'B', 'yellow': 'G1', 'whiteRet': 'G1'}
RGB = dict(white='ffffff', red='ff0000', green='00ff00', blue='0000ff', yellow='ffff00', whiteRet='ffffff')
SHORT = (125000, 200000, 312500)
LONG = 500000
PHASES = {f'b{ns}_{c}': (c, ns) for c in PRIMARY for ns in (*SHORT, LONG)}
SCALES = np.arange(30, 141) / 10.  # R35 grid: µs per native RAW row, *not* per CFA cell


def candidate(p, smooth=21, wing=15):
    """R35.event after site qualification/detrending; return center or reason plus an edge flag."""
    lag, radius = 90, 145  # Bayer cells; fixed 291-sample input required by R35 cost
    sm = np.convolve(np.pad(p, smooth//2, mode='edge'), np.ones(smooth)/smooth, 'valid')
    deficit = (sm[:-2*lag] + sm[2*lag:])/2 - sm[lag:-lag]
    peaks = 1 + lag + np.flatnonzero((deficit[1:-1] >= deficit[:-2]) &
                                      (deficit[1:-1] > deficit[2:]) & (deficit[1:-1] > .10))
    full = peaks[(peaks >= radius) & (peaks < len(p)-radius)]
    # The two-sided lag detector cannot see centers in its first/last 90 cells.
    # A dark edge run is a censoring flag only; never extrapolate its center.
    edge = len(full) != len(peaks) or min(sm[:lag].min(), sm[-lag:].min()) < .80
    if not len(full):
        return None, 'no_complete_candidate' if edge else 'no_strong_candidate', edge
    i = int(full[np.argmax(deficit[full-lag])])
    seg = p[i-radius:i+radius+1]
    if min(seg[:wing].mean(), seg[-wing:].mean()) - seg[100:191].min() < .12:
        return None, 'weak_wings', edge
    return i, 'ok', edge


def event(path, site, ns):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['width'], m['height'], m['orientation'], m['cfa_pattern_2x2'],
         m['focal_length_mm'], m['iso']) != ('Nothing', 'A001', 4080, 3072, 1, [1, 2, 0, 1], 5.56, 6400)
            or not abs(m['exposure_us']*1000 - ns) <= 1):
        raise ValueError('unexpected camera geometry, ISO or exposure')
    i = dict(SITES)[site]
    dy, dx = divmod(i, 2)
    y0, y1, x0, x1 = ROI
    plane = raw[2*y0+dy:2*y1:2, 2*x0+dx:2*x1:2]
    p = plane.mean(axis=1) - m['black_levels'][i]
    gate = ('clipped' if np.any(plane >= m['white_level']) else 'storage_floor' if np.any(plane == 0)
            else 'below_20dn' if p.mean() < 20 else 'ok')
    if gate != 'ok':
        return None, (gate,)
    x = np.arange(len(p))
    baseline = np.polyval(np.polyfit(x, p, 2), x)
    if np.min(baseline) <= 0:
        return None, ('nonpositive_baseline',)
    p = p / baseline
    center, reason, edge = candidate(p)
    flags = [reason]
    if edge:
        flags.append('edge_candidate')
    for name, settings in [('smooth_sensitive', [(11, 15), (31, 15)]),
                           ('wing_sensitive', [(21, 10), (21, 25)])]:
        for smooth, wing in settings:
            alt = candidate(p, smooth, wing)[0]
            if ((center is None) != (alt is None) or
                    (center is not None and alt is not None and abs(center-alt) > 8)):
                flags.append(name)
                break
    selected = None if center is None else (m['exposure_us'], p[center-145:center+146])
    return selected, flags


def fit(short, long):
    pairs = [(u, v) for u in short for v in long]
    out = dict(short_n=len(short), long_n=len(long), pairs=0, status='skipped_too_few_complete')
    if min(len(short), len(long)) < 2:
        return out
    out['pairs'] = len(pairs)
    with np.errstate(divide='ignore', invalid='ignore'):
        losses = np.array([[cost(u, v, s) for s in SCALES] for u, v in pairs])
    if not np.isfinite(losses).all():
        return dict(out, status='skipped_nonfinite_loss')
    curve = np.median(losses, axis=0)
    j = int(curve.argmin())
    individual = SCALES[losses.argmin(axis=1)]
    near = SCALES[curve <= curve[j] + .001]  # within 0.1 percentage point of best shape R²
    edge = j == 0 or j == len(SCALES)-1
    # Operational identification gates; even a perfect shape correlation is
    # uninformative if many very different gradients match it equally well.
    if edge:
        status = 'skipped_search_edge'
    elif 1-curve[j] < .95:
        status = 'skipped_poor_shape'
    elif near.min() == SCALES[0] or near.max() == SCALES[-1] or np.ptp(near) > .5*SCALES[j]:
        status = 'skipped_flat_minimum'
    elif np.ptp(individual) > .5*SCALES[j]:
        status = 'skipped_pair_disagreement'
    else:
        status = 'ok'
    out.update(status=status, effective_us_per_raw_row=SCALES[j] if status == 'ok' else None,
               pair_median=round(float(np.median(individual)), 2), pair_min=individual.min(), pair_max=individual.max(),
               median_shape_r2_pct=round(100*(1-curve[j]), 3), search_edge=int(edge),
               individual_edge_n=int(np.isin(individual, SCALES[[0, -1]]).sum()),
               near_min=near.min(), near_max=near.max())
    return out


def check_windows(path):
    seen = set()
    with path.open(newline='') as f:
        for r in csv.DictReader(f, strict=True):
            ph = r['phase']
            if ph not in PHASES:
                continue
            scene, ns = PHASES[ph]
            if (ph in seen or (r['profile'], r['scene_rgb'], r['sysfs_bl'], r['hwc_both'], r['group_both'],
                               r['frames'], r['exposure_ns']) !=
                    ('active_0x8e', RGB[scene], '6692', '0', '0x3', '3', str(ns)) or
                    not abs(float(r['refresh_both'])-120) <= .05):
                raise ValueError(f'invalid window receipt: {ph}')
            seen.add(ph)
    if seen != PHASES.keys():
        raise ValueError('incomplete daytime windows.csv')


def analyze(frames):
    paths = inputs(frames)
    groups, counts = {}, {}
    for ph in PHASES:
        if {n for phase, n in paths if phase == ph} != {1, 2, 3}:
            raise ValueError(f'incomplete daytime matrix: expected {ph}__1..3.dng')
    for ph, (scene, ns) in PHASES.items():
        groups[scene, ns] = selected = []
        counts[scene, ns] = count = Counter()
        for n in (1, 2, 3):
            try:
                value, flags = event(paths[ph, n], PRIMARY[scene], ns)
            except ValueError as exc:
                raise ValueError(f'{ph}/{n}: {exc}') from None
            count.update(flags)
            if value is not None:
                selected.append(value)
    for scene, site in PRIMARY.items():
        for ns in SHORT:
            row = dict(scene=scene, site=site, short_us=ns/1000, long_us=LONG/1000)
            row.update(fit(groups[scene, ns], groups[scene, LONG]))
            for side, t in [('short', ns), ('long', LONG)]:
                row[side+'_selection'] = ';'.join(f'{k}:{v}' for k, v in sorted(counts[scene, t].items()))
            yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--windows', type=Path, metavar='windows.csv', help='check the bound R41 daytime receipts')
    args = ap.parse_args()
    try:
        if args.windows:
            check_windows(args.windows)
        rows = list(analyze(args.frames))  # no partial CSV on invalid input
    except OSError as exc:
        ap.error(exc.strerror)
    except (KeyError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    cols = ('scene site short_us long_us short_n long_n pairs status effective_us_per_raw_row '
            'pair_median pair_min pair_max median_shape_r2_pct search_edge individual_edge_n '
            'near_min near_max short_selection long_selection').split()
    out = csv.DictWriter(sys.stdout, fieldnames=cols, lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
