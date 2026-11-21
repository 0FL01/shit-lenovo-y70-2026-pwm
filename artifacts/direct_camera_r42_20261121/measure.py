#!/usr/bin/env python3
"""R42: python3 -B measure.py FRAMES > frames.csv. One row per phase__N.dng.

Native A001 GBRG. All DN are signed after the site's tagged BlackLevel; raw
floor/clip counts refer to stored samples. Percentiles follow R41 (5x5 blocks;
P01/P90 on block-row means, no flat). All depths use one G1-selected physical
RAW row in this exposure, never a separately minimized half or color. FWHM is
in physical sensor rows, not time. Blank metrics have an explicit status.
"""

import argparse
from collections import Counter
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r36_20261120.channels import characterize
from direct_camera_r41_20261121.measure import (
    SITES, decode_dng_bytes, extract_metadata, inputs, row_notch,
)
from direct_camera_r42_20261121.geometry import EXPECTED_ORIENTATION


ROI = (630, 1250, 754, 799)  # half-open native 2x2 cells; freeze from CAL
SCENES = ('full', 'core', 'loaded', 'coreRet', 'loadedRet', 'fullRet', 'ring', 'inverse', 'dark')
DAY_US = {'d312': 312.5, 'd200': 200., 'd500': 500.}
GROUPS = ('cal', *DAY_US, 'e_flat', 'e_short')


def phase_info(phase):
    tokens = phase.split('_')
    scenes = [s for s in tokens if s in SCENES]
    if len(scenes) != 1 or '' in tokens:
        raise ValueError('expected exactly one R42 scene token')
    scene, = scenes
    return scene, '_'.join(s for s in tokens if s != scene)


def read_sites(path, expected_us):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['focal_length_mm'], m['orientation'],
         m['width'], m['height'], raw.shape, m['cfa_pattern_2x2'], m['iso']) !=
            ('Nothing', 'A001', 5.56, EXPECTED_ORIENTATION.get(), 4080, 3072, (3072, 4080), [1, 2, 0, 1], 6400)):
        raise ValueError('unexpected camera, native geometry, CFA, lens or ISO')
    us = m['exposure_us']
    if not np.isfinite(us) or us <= 0 or (expected_us is not None and abs(us-expected_us) > .001):
        raise ValueError(f'unexpected exposure {us:g} us (expected {expected_us} us)')
    y0, y1, x0, x1 = ROI
    h, w = y1-y0, x1-x0
    if not (0 <= y0 < y1 <= raw.shape[0]//2 and 0 <= x0 < x1 <= raw.shape[1]//2
            and h >= 400 and w >= 40 and h % 5 == w % 5 == 0):
        raise ValueError('ROI must be in bounds, >=400x40 cells, extents divisible by 5')
    return m, {site: raw[2*y0+i//2:2*y1:2, 2*x0+i%2:2*x1:2] for site, i in SITES}


def sample(stored, black, white, control):
    signal = stored.astype(float) - black
    mean = signal.mean()
    clip, floor = np.count_nonzero(stored >= white), np.count_nonzero(stored == 0)
    gate = ('clipped' if clip else 'storage_floor' if floor else 'control' if control
            else 'below_20dn' if mean < 20 else 'ok')
    return signal, dict(mean_dn=mean, clip_n=clip, floor_n=floor, gate=gate)


def fixed_event(signal, dy, event):
    """R36 fixed-row amplitude, with bounded relative-half-depth crossings.

    R36's ±30 RAW-row center diagnostic can truncate a moderate, broad notch.
    Walk outwards from this anchor only, inside the 81-cell plateau window
    AND the R33 valid interior. No 0.70-plateau threshold, edge padding, or
    fallback to a different minimum. An odd CFA row is interpolated at event.
    """
    y0, y1, _, _ = ROI
    rows = 2*np.arange(y0+1, y1-1) + dy
    unsmoothed = signal.mean(axis=1)
    prof = np.convolve(unsmoothed, np.ones(3)/3, 'valid')
    k = int(np.argmin(abs(rows-event)))
    if not rows[40] <= event <= rows[-41]:
        return 'incomplete_window', {}
    try:
        plateau, at, depth, _, _ = characterize(rows, prof, event)
    except ValueError:
        return 'invalid_plateau', {}
    if plateau < 20:
        return 'low_local_plateau', {}
    # R41's prespecified robust noise check on shoulders 16..40 cells away.
    shoulders = np.r_[prof[k-40:k-15], prof[k+16:k+41]]
    mad = np.median(abs(shoulders - np.median(shoulders)))
    if plateau-at <= max(1., 5 * 1.4826 * mad):  # at least one stored DN even on noiseless shoulders
        return 'weak_event', {}

    low, high = max(40, k-40), min(len(rows)-41, k+40)
    x, p = rows[low:high+1], prof[low:high+1]
    def crossings(half):
        left = np.flatnonzero((x < event) & (p >= half))
        right = np.flatnonzero((x > event) & (p >= half))
        if not left.size or not right.size:
            return None
        l, r = left[-1], right[0]
        xl = np.interp(half, p[[l+1, l]], x[[l+1, l]])
        xr = np.interp(half, p[r-1:r+1], x[r-1:r+1])
        return xl, xr, l, r

    bounds = crossings((plateau+at)/2)
    if bounds is None:
        return 'unbounded_event', {}
    # For a half/site, ensure the anchor is actually inside the half-depth
    # interval of this connected dip, not sitting on a weak tail next to it.
    _, _, l, r = bounds
    bottom = p[l+1:r]
    if not bottom.size or at >= (half := (plateau+bottom.min())/2):
        return 'anchor_off_dip', {}
    xl, xr, _, _ = crossings(half)  # crossings already exist for the higher level
    # A single bad native row becomes three equally low samples after the
    # boxcar. Require native support as well as a >=3-cell smoothed width.
    support = (rows >= xl) & (rows <= xr) & (unsmoothed[1:-1] < half)
    if xr-xl < 6 or np.count_nonzero(support) < 3:
        return 'too_narrow', {}
    if min(np.median(shoulders[:25]), np.median(shoulders[25:])) <= half:
        return 'ambiguous_shoulders', {}
    if plateau+at <= 0:
        return 'invalid_michelson_denominator', {}
    return 'ok', dict(local_plateau_dn=plateau, min_dn=at, depth_pct=depth,
                      michelson_pct=100*(plateau-at)/(plateau+at), fwhm_raw_rows=xr-xl)


def measure(phase, n, path, exposure=None):
    scene, group = phase_info(phase)
    m, planes = read_sites(path, exposure)
    control = scene in ('ring', 'inverse', 'dark')  # ROI is black in all three
    y0, y1, x0, x1 = ROI
    row = dict(phase=phase, scene=scene, group=group, frame_n=n, exposure_us=m['exposure_us'],
               iso=m['iso'], width=m['width'], height=m['height'], orientation=m['orientation'],
               focal_mm=m['focal_length_mm'], cfa='GBRG', y0=y0, y1=y1, x0=x0, x1=x1,
               black_dn=m['black_levels'][0], white_dn=m['white_level'])
    white = m['white_level']
    green, stats = sample(planes['G1'], row['black_dn'], white, control)
    row.update(stats)
    blocks = green.reshape((y1-y0)//5, 5, (x1-x0)//5, 5).mean(axis=(1, 3))
    p5, p95 = np.percentile(blocks, (5, 95))
    p1, p90 = np.percentile(blocks.mean(axis=1), (1, 90))
    usable = stats['gate'] == 'ok'
    row.update(block_p05_dn=p5, block_p95_dn=p95, row_p01_dn=p1, row_p90_dn=p90,
               block_contrast_pct=100*(p95-p5)/(p95+p5) if usable and p95+p5 > 0 else None,
               row_p01_dip_pct=100*(1-p1/p90) if usable and p90 > 0 else None)

    notch = row_notch(green, y0, usable)
    event = notch['notch_center_raw_y']
    row['candidate_raw_y'] = event  # diagnostic only; may be unqualified
    status = stats['gate'] if not usable else 'no_candidate' if event is None else 'ok'
    metrics = {}
    if status == 'ok':
        status, metrics = fixed_event(green, 0, event)
    half_statuses = []
    mid = green.shape[1]//2
    for side, sl in [('left', slice(None, mid)), ('right', slice(mid, None))]:
        half, counts = sample(planes['G1'][:, sl], row['black_dn'], white, control)
        row.update({side+'_'+k: v for k, v in counts.items()})
        check, values = counts['gate'], {}
        if check == 'ok':
            check, values = fixed_event(half, 0, event) if status == 'ok' else ('no_g1_event', {})
        row[side+'_status'] = check
        row[side+'_depth_pct'] = values.get('depth_pct')
        half_statuses.append(check)
    if status == 'ok' and half_statuses != ['ok', 'ok']:
        status = 'half_check_failed'
    row.update(event_status=status, fixed_g1_raw_y=event if status == 'ok' else None)
    for key in ('local_plateau_dn', 'min_dn', 'depth_pct', 'michelson_pct', 'fwhm_raw_rows'):
        row[key] = metrics.get(key) if status == 'ok' else None

    for site, i in SITES:
        if site == 'G1':
            continue
        signal, counts = sample(planes[site], m['black_levels'][i], white, control)
        prefix = site.lower() + '_'
        row.update({prefix+k: v for k, v in counts.items()})
        check, values = counts['gate'], {}
        if check == 'ok':
            check, values = fixed_event(signal, i//2, event) if status == 'ok' else ('no_g1_event', {})
        row.update({prefix+'status': check, prefix+'depth_pct': values.get('depth_pct')})
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    for group in ('cal', 'flat', 'short'):
        ap.add_argument('--'+group+'-us', type=float, help='also require this exposure for '+group)
    args = ap.parse_args()
    expected = {**DAY_US, 'cal': args.cal_us, 'e_flat': args.flat_us, 'e_short': args.short_us}
    if any(v is not None and not (np.isfinite(v) and v > 0) for v in expected.values()):
        ap.error('expected exposures must be finite and positive')
    rows, actual = [], {}
    try:
        for (phase, n), path in sorted(inputs(args.frames).items()):
            try:
                if n < 1:
                    raise ValueError('frame indices must be positive')
                _, group = phase_info(phase)
                # Unless explicitly specified, require the first observed tag
                # throughout the acquisition group (including other scenes).
                target = expected.get(group)
                row = measure(phase, n, path, target if target is not None else actual.get(group))
                actual.setdefault(group, row['exposure_us'])
                rows.append(row)
            except ValueError as exc:
                raise ValueError(f'{phase}/{n}: {exc}') from None
        if 'e_flat' in actual and 'e_short' in actual and actual['e_flat'] <= actual['e_short']:
            raise ValueError('e_flat exposure must exceed e_short')
    except (ValueError, OSError) as exc:
        ap.error(exc.strerror if isinstance(exc, OSError) else str(exc))

    phase_n = Counter(r['phase'] for r in rows)
    ok_n = Counter(r['phase'] for r in rows if r['event_status'] == 'ok')
    group_n = Counter(r['group'] for r in rows)
    rows.sort(key=lambda r: (GROUPS.index(r['group']) if r['group'] in GROUPS else len(GROUPS),
                             r['group'], SCENES.index(r['scene']), r['phase'], r['frame_n']))
    for r in rows:
        r.update(phase_n=phase_n[r['phase']], phase_ok_n=ok_n[r['phase']], group_n=group_n[r['group']])
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for r in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in r.items()})


if __name__ == '__main__':
    main()
