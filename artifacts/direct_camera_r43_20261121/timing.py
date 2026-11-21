#!/usr/bin/env python3
"""R43: python timing.py FRAMES > timing.csv. Use an accepted daytime archive.

frame rows: G1 of R42's fixed ROI, one shutter release at a time. A broad run
is >=3 cells below 0.70 of the local median (3-cell smoothing, 81-cell median
as in R33). Near an ROI edge use only observed cells for the median. Require
both crossings, ten measured bright shoulder cells on either side (median
ratio >=0.80), >=20 DN plateau and coincident runs in both horizontal halves.
Bounds are inclusive RAW rows below threshold; center = midpoint of bounds.
interior_n counts the subset also bounded inside R33's full-median interior.
Only adjacent qualified runs in the SAME frame supply spacing. A blank is not
zero. deficit_us is the R43 deepest qualified local dip's exposure * fractional
depth: equivalent missing plateau light during integration, NOT panel off-time.

fit rows: one isolated R41 candidate (291 unsmoothed cells) at most per DNG,
selected by R41's own wing/contrast checks independently of the 0.70 spacing cut;
two distinct DNGs at each exposure, same scene, no pooling of SDR and return.
R41 fits R35's commuting exposure boxes; its shape, search-edge, flatness and
pair-disagreement gates apply. This estimates a local camera/display effective
phase gradient, not sensor line time. Pair counts reuse frames, not independent
sample sizes. Conditional repeat interval assumes stationary recurring notches
and locally constant gradient; require within-frame gaps in >=2 DNGs of the
matched exposures, agreeing within 10% across all gaps. No HWC timing input,
no claim of physical PWM frequency. Filenames identify acquisition windows;
display-state qualification belongs to windows.py.
"""
import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r41_20261121.blur import candidate, fit
from direct_camera_r42_20261121.measure import ROI, fixed_event, inputs, read_sites, row_notch, sample


SCENES = ('sdr', 'hdr', 'sdrRet', 'sdrHigh')
US = {'125': 125., '200': 200., '312': 312.5, '500': 500.}
FIELDS = ('kind scene frame exposure_us status complete_n interior_n bounds_raw_rows gaps_raw_rows '
          'rejected blur_status deficit_status deficit_us short_us long_us short_frames long_frames '
          'short_n long_n pairs effective_us_per_raw_row pair_median pair_min pair_max '
          'median_shape_r2_pct search_edge individual_edge_n near_min near_max spacing_frames '
          'period_status spacing_median_raw_rows conditional_period_us').split()


def runs(signal):
    """Indices are in original Bayer cells (the valid 3-cell filter starts at 1)."""
    p = signal.mean(axis=1)
    sm = np.convolve(p, np.ones(3)/3, 'valid')
    half = 40
    median = np.r_[[np.median(sm[:i+half+1]) for i in range(half)],
                   np.median(sliding_window_view(sm, 81), axis=1),
                   [np.median(sm[i-half:]) for i in range(len(sm)-half, len(sm))]]
    ratio = np.divide(sm, median, out=np.full_like(sm, np.nan), where=median > 0)
    change = np.diff(np.r_[False, ratio < .70, False].astype(int))
    result = []
    for a, b in zip(np.flatnonzero(change == 1), np.flatnonzero(change == -1)):
        if b-a < 3:
            continue
        # b is exclusive in the smoothed profile; [a+1,b] in native cells.
        if a < 10 or b+10 > len(sm):
            status = 'edge_or_short_wing'
        elif np.min(median[a:b]) < 20:
            status = 'low_plateau'
        elif not all(np.median(s) >= .80 for s in (ratio[a-10:a], ratio[b:b+10])):
            status = 'weak_wing'
        elif np.count_nonzero(p[a+1:b+1] < .70*median[a:b]) < 3:
            status = 'too_few_native_cells'
        else:
            status = 'ok'
        result.append((a+1, b, status))
    return result


def spacing(green):
    halves = np.hsplit(green, [green.shape[1]//2])
    sides = [runs(h) for h in halves]
    qualified, gaps, rejected = [], [], []
    previous = None
    for a, b, status in runs(green):
        mid = (a+b)/2
        if status == 'ok' and not all(any(s == 'ok' and l <= mid <= r and a <= (l+r)/2 <= b
                                          for l, r, s in side) for side in sides):
            status = 'half_check_failed'
        if status != 'ok':
            rejected.append(status)
            previous = None  # never count a gap across a rejected broad candidate
            continue
        qualified.append((a, b))
        if previous is not None:
            gaps.append(2*(mid-previous))
        previous = mid
    return qualified, gaps, rejected


def frame(path, scene, expected, seen):
    m, planes = read_sites(path, expected)
    # inputs() rejects repeated inodes; also reject renamed copies when counting
    # independent shutters. Identical raw G1 samples cannot add a replicate.
    key = blake2b(planes['G1'].tobytes(), digest_size=16).digest()
    if key in seen:
        raise ValueError('repeated raw G1 samples')
    seen.add(key)
    g, q = sample(planes['G1'], m['black_levels'][0], m['white_level'], False)
    us = m['exposure_us']
    row = dict(kind='frame', scene=scene, frame=path.stem, exposure_us=us, status=q['gate'])
    if q['gate'] != 'ok':
        return row, None, []
    accepted, gaps, rejected = spacing(g)
    y0 = ROI[0]
    row.update(complete_n=len(accepted), interior_n=sum(a > 41 and b < len(g)-42 for a, b in accepted),
               bounds_raw_rows=';'.join(f'{2*(y0+a)}:{2*(y0+b)}' for a, b in accepted),
               gaps_raw_rows=';'.join(f'{v:g}' for v in gaps), rejected=';'.join(rejected))

    if expected == 500:
        # Reuse the R43 amplitude anchor, independently of the R41 long wings.
        anchor = row_notch(g, y0, True)['notch_center_raw_y']
        status, values = fixed_event(g, 0, anchor) if anchor is not None else ('no_candidate', {})
        if status == 'ok':
            for h in np.hsplit(g, [g.shape[1]//2]):
                if h.mean() < 20 or fixed_event(h, 0, anchor)[0] != 'ok':
                    status = 'half_check_failed'
                    break
        row['deficit_status'] = status
        if status == 'ok':
            row['deficit_us'] = us*values['depth_pct']/100

    p = g.mean(axis=1)
    x = np.arange(len(p))
    bg = np.polyval(np.polyfit(x, p, 2), x)
    value = None
    reason = 'nonpositive_baseline'
    if np.min(bg) > 0:
        norm = p/bg
        center, reason, _ = candidate(norm)
        if center is not None:
            value = us, norm[center-145:center+146]
    row['blur_status'] = reason
    return row, value, gaps


def analyze(directory):
    paths = inputs(directory)
    seen = set()
    scenes = {s: US for s in SCENES}
    # 120-fps acquisition uses e.g. day_sdr120_125. Never borrow 500 us from day_sdr.
    for name in ('sdr120', 'hdr120', 'sdrRet120', 'sdrMatch', 'hdrAgain'):
        if any(ph.startswith(f'day_{name}_') for ph, _ in paths):
            scenes[name] = {k: US[k] for k in (('200', '312') if name == 'hdrAgain' else ('125', '200', '312'))}
    phases = {f'day_{s}_{k}' for s, times in scenes.items() for k in times}
    if not any(ph in phases for ph, _ in paths):
        raise ValueError('no R43 daytime timing windows')
    for scene, times in scenes.items():
        events, spacings, counts = {}, {}, {}
        for token, us in times.items():
            phase = f'day_{scene}_{token}'
            events[token], spacings[token], counts[token] = [], [], 0
            for (ph, n), path in sorted(paths.items()):
                if ph != phase:
                    continue
                try:
                    if n < 1:
                        raise ValueError('nonpositive frame index')
                    row, event, gaps = frame(path, scene, us, seen)
                except ValueError as exc:
                    raise ValueError(f'{path.name}: {exc}') from None
                counts[token] += 1
                if event is not None:
                    events[token].append(event)
                if gaps:
                    spacings[token].append(gaps)
                yield row

        long = '500' if '500' in times else '312'
        for short in times:
            if short == long:
                continue
            row = fit(events[short], events[long])
            row.update(kind='fit', scene=scene, short_us=US[short], long_us=US[long],
                       short_frames=counts[short], long_frames=counts[long])
            if min(counts[short], counts[long]) == 0:
                row['status'] = 'skipped_missing_window'
            elif long == '312' and row['status'] == 'ok' and row['individual_edge_n']:
                # Less blur leverage without a 500-us shutter: do not accept a
                # group estimate if even one pair prefers the search boundary.
                row.update(status='skipped_individual_search_edge', effective_us_per_raw_row=None)
            frames = spacings[short]+spacings[long]
            row['spacing_frames'] = len(frames)
            if row['status'] != 'ok':
                period = 'no_qualified_scale'
            elif len(frames) < 2:
                period = 'too_few_within_frame_spacings'
            elif np.ptp(np.concatenate(frames)) > .10*np.median(np.concatenate(frames)):
                period = 'inconsistent_within_frame_spacings'
            else:
                # Weight shutter releases equally, not frames with more gaps more heavily.
                dx = np.median([np.median(gaps) for gaps in frames])
                row.update(spacing_median_raw_rows=dx, conditional_period_us=dx*row['effective_us_per_raw_row'])
                period = 'conditional'
            yield dict(row, period_status=period)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    args = ap.parse_args()
    try:
        rows = list(analyze(args.frames))
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
