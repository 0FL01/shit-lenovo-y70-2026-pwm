#!/usr/bin/env python3
"""R46: python3 -B timing.py FRAMES strip.csv > timing.csv
Secondary: python3 -B timing.py --extended CONFIRM_FRAMES extended.csv > extended_timing.csv

Use only the independently CAL-qualified G1 strip. Coordinates y0,y1,x0,x1
are half-open Bayer cells; all reported centers, widths and gaps are native
RAW rows. A failed/missing strip is not permission to use the primary ROI.
The display/HDR/ON and acquisition bracket receipts are checked by windows.py.
Extended mode replays extended.py on this archive's 4-ms CALs: selection by
A/B only, C held out. Recompute every fit and spacing on that one common ROI.

Spatial: R43's local-median 0.70 runs, observed crossings and wings, full G1
and both halves. At each run additionally require two >=20 DN shoulder levels
and a connected half-depth dip >=12 RAW rows with >=6 native cells of support.
Use a sloping line between the measured shoulders to estimate center/FWHM.
Keep the strip design's 100-cell outer clearance for a pair. Never bridge a
rejected run, a contradictory half, or an underlit gap. Widths
are exposure-integrated strip diagnostics, not the primary-ROI depth/widths.

Identity: independently check the strip for the R44 light-row fine component.
For timing require the free search AND the 177.35/188.50 RAW-row controls below
their empirical gates (<15% semi-amplitude, half the 0.30 run-depth cut).
Unresolved for lack of light cycles is not a negative control. Finite-band
sensitivity, not an exclusion of all carriers. Keep morphology diagnostics
when this screen fails; never use those widths/gaps as identified events.

Scale: one unsmoothed R41 291-cell shape per independent DNG, no stacking.
Both wings >=20 DN, one isolated half-depth core in the cutout in full G1
and each half. This fit is independent of the 0.70 spacing threshold. Apply
all R41 commuting-box gates; additionally reject any individual search edge.
Short calibration: 200/500 checked by 312.5/500 within 10%. In the separate
confirm bracket, six independent DAY/1250 releases per state also allow a long
calibration: 312.5/1250 checked by 500/1250 within 10%. Same R41 loss, finite
cutout/constant-wing model and quality gates. CALs are never blur inputs. The
two checks within a family share long exposures, not independent error bars.
Use either qualified family; if both qualify their lead estimates must also
agree within 10% (range / mean of the two), then retain the original 200/500.
Only 200/312.5/500 supply widths and gaps. apparent_fwhm_us is the qualified
exposure-integrated strip FWHM times this state's selected gradient.
At least two distinct DNG releases must supply adjacent same-frame center gaps
agreeing within 10% across all such gaps; weight frames equally. A conditional
repeat period assumes stationary identical broad events and a constant local
camera/display gradient. Its reciprocal is not physical fine-PWM Hz; neither
an intrinsic off-time nor a physical frequency bound follows from this test.
"""
import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r41_20261121.blur import candidate, fit
from direct_camera_r42_20261121.measure import inputs
from direct_camera_r43_20261121.timing import runs
from direct_camera_r44_20261121.fine import assess, free_fit
from direct_camera_r46_20261121.fine import ANCHORS
from direct_camera_r46_20261121 import strip


STATES = ('on120A', 'on144B', 'on120C')
US = {'200': 200., '312': 312.5, '500': 500., '1250': 1250.}
FIELDS = ('kind state phase frame_n exposure_us frame_role strip_status y0 y1 x0 x1 status mean_dn '
          'left_mean_dn right_mean_dn clip_n floor_n fine_status free_status '
          'free_semiamp_pct free_gate_pct r35_177p35_status r35_177p35_gate_pct '
          'r35_188p50_status r35_188p50_gate_pct '
          'morph_n broad_n bounds70_raw_y centers_raw_y fwhm_raw_rows apparent_fwhm_us rejected gaps_raw_rows '
          'blur_status blur_center_raw_y blur_other_edge_flag scale_family short_us long_us short_n long_n pairs '
          'effective_us_per_raw_row pair_median pair_min pair_max median_shape_r2_pct search_edge '
          'individual_edge_n near_min near_max short_scale_status short_scale_us_per_raw_row '
          'day_1250_n long_scale_status long_scale_us_per_raw_row cross_scale_status '
          'scale_status scale_source spacing_status spacing_frames spacing_n '
          'spacing_min_raw_rows spacing_max_raw_rows spacing_median_raw_rows '
          'conditional_period_us physical_pwm_hz_status').split()


def receipts(f, states=STATES, confirm=False, extended=False):
    """Consume strip.py's state receipts, not geometry.csv from the primary ROI."""
    reader = csv.DictReader(f, strict=True)
    required = {'state', 'status', 'guard', 'y0', 'y1', 'x0', 'x1'}
    if extended:
        required.update(('field_us', 'qualified_us'))
    if not required.issubset(reader.fieldnames or ()):
        raise ValueError('strip.csv requires ' + ','.join(sorted(required)))
    result = {}
    for r in reader:
        state, status = r['state'], r['status']
        if state not in states or state in result or not status:
            raise ValueError(f'{state}: unexpected or duplicate strip receipt or empty status')
        if status != 'PASS':
            result[state] = status, None
            continue
        if extended and r.get('state_field_status', 'PASS') != 'PASS':
            result[state] = r['state_field_status'], None
            continue
        if extended and r.get('selection', 'AB_CAL_only_C_holdout') != 'AB_CAL_only_C_holdout':
            raise ValueError(f'{state}: unexpected extended selection protocol')
        if (confirm or extended) and (r.get('field_us'), r.get('qualified_us')) != ('4000', '4000'):
            result[state] = 'CONFIRM_REQUIRES_4000_CAL', None
            continue
        roi = tuple(int(r[k]) for k in ('y0', 'y1', 'x0', 'x1'))
        if extended:
            y0, y1, x0, x1 = roi
            a, b, left, right = strip.ROI
            if not (int(r['guard']) == strip.GUARD and (x0, x1) == (left, right)
                    and strip.GUARD <= y0 <= a and b <= y1 <= 3072//2-strip.GUARD
                    and (a-y0) % 10 == (y1-b) % 10 == 0):
                raise ValueError(f'{state}: invalid extended strip (fixed x, guarded 10-cell y grid required)')
        elif roi != strip.ROI or int(r['guard']) != strip.GUARD:
            raise ValueError(f'{state}: not the frozen timing strip and guard')
        result[state] = status, roi
    for state in states:
        result.setdefault(state, ('MISSING_CAL', None))
    if extended and len({roi for _, roi in result.values() if roi is not None}) > 1:
        raise ValueError('extended strip differs between states')
    if any(roi is None for _, roi in result.values()):
        # strip.require_geometry(): do not transfer a CAL pass from a different
        # leg of the R46 bracket, or claim the full strip passed when it didn't.
        result = {s: (('BLOCKED_OTHER_CAL', None) if roi is not None else (st, None))
                  for s, (st, roi) in result.items()}
    return result


def verify_extended(frames, strips):
    """Bind the coordinate receipt to *this* A/B selection and one-shot C field check."""
    from direct_camera_r46_20261121.extended import run

    actual = {}
    for row in run(frames):  # CAL only; no DAY paths or timing metrics passed to the selector
        if (row['status'], row['state_field_status'], row['field_us'], row['qualified_us'], row['guard']) != (
                'PASS', 'PASS', 4000, 4000, strip.GUARD):
            raise ValueError(f"{row['state']}: replay of extended CAL did not pass: {row['status']}")
        actual[row['state']] = 'PASS', tuple(row[k] for k in ('y0', 'y1', 'x0', 'x1'))
    if actual != strips:
        raise ValueError('extended receipt differs from the A/B-only CAL choice with held-out C in this archive')


def series(xs):
    return ';'.join(f'{v:.7g}' for v in xs)


def shade(p):
    x = np.linspace(-1, 1, len(p))
    return np.polyval(np.polyfit(x, p, 2), x)


def fine_gate(g, p, bg):
    a, b = g[:, ::2], g[:, 1::2]
    noise = (a.mean(1)-b.mean(1))*np.sqrt(a.shape[1]*b.shape[1])/g.shape[1]
    data = (np.column_stack((p, noise))/bg[:, None], bg)
    fits = [free_fit(data), *(assess(data, pitch) for pitch in ANCHORS.values())]
    row = dict(free_semiamp_pct=fits[0].get('fit_semiamp_pct'))
    for key, value in zip(('free', *ANCHORS), fits):
        row[key+'_status'] = value['status']
        row[key+'_gate_pct'] = value.get('gate_semiamp_pct')
    ok = all(v['status'] == 'below_empirical_gate' and v['gate_semiamp_pct'] < 15 for v in fits)
    return dict(row, fine_status='below_strip_gates' if ok else 'ambiguous_fine_component')


def half_depth(p, a, b):
    """Native-cell half-depth crossings on valid 3-cell averages with local tilt removed."""
    if a-24 < 1 or b+24 >= len(p)-1:
        return None, 'edge_shoulder'
    x = np.arange(a-24, b+25)
    sm = np.convolve(p[x[0]-1:x[-1]+2], np.ones(3)/3, 'valid')
    left, right = np.median(sm[:20]), np.median(sm[-20:])
    if min(left, right) < 20:
        return None, 'dim_shoulder'
    bg = np.interp(x, [x[0]+9.5, x[-1]-9.5], [left, right])
    v = sm/bg
    k = 24 + np.argmin(v[24:len(x)-24])
    level = (1+v[k])/2
    shoulders = np.r_[v[:20], v[-20:]]
    mad = np.median(abs(shoulders-np.median(shoulders)))
    if 1-v[k] <= max(1/min(left, right), 5*1.4826*mad):
        return None, 'weak_local_dip'
    l, r = np.flatnonzero(v[:k] >= level), np.flatnonzero(v[k+1:] >= level)
    if not len(l) or not len(r):
        return None, 'unbounded_half_depth'
    l, r = l[-1], k+1+r[0]
    xl = np.interp(level, v[[l+1, l]], x[[l+1, l]])
    xr = np.interp(level, v[r-1:r+1], x[r-1:r+1])
    if xr-xl < 6 or np.count_nonzero((xl < x) & (x < xr) & (p[x] < level*bg)) < 6:
        return None, 'too_narrow_native'
    return (xl, xr), 'ok'


def morphology(parts, profiles, y0):
    detections = [runs(h) for h in parts]
    kept, gaps, rejected = [], [], []
    previous = None
    for a, b, status in detections[0]:
        bounds = None
        if status == 'ok':
            bounds, status = half_depth(profiles[0], a, b)
        if status == 'ok':
            centers = [np.mean(bounds)]
            cross = [bounds]
            for p, side in zip(profiles[1:], detections[1:]):
                matches = [(l, r) for l, r, s in side if s == 'ok' and l <= (a+b)/2 <= r and a <= (l+r)/2 <= b]
                if len(matches) != 1:
                    status = 'half_run_mismatch'
                    break
                h, reason = half_depth(p, *matches[0])
                if h is None:
                    status = 'half_'+reason
                    break
                centers.append(np.mean(h))
                cross.append(h)
            if status == 'ok' and (min(centers) < max(l for l, _ in cross) or max(centers) > min(r for _, r in cross)):
                status = 'half_center_mismatch'
        if status != 'ok':
            rejected.append(f'{2*(y0+a)}:{2*(y0+b)}:{status}')
            previous = None
            continue
        center = np.mean(bounds)
        kept.append((a, b, center, 2*(bounds[1]-bounds[0])))
        if previous is not None:
            first, lo, pc = previous
            # An intervening dark area at insufficient local light can hide a
            # release. Do not declare adjacency across it. Use covered cells
            # only, at the same 81-cell local background scale as R43.
            valid_background = (a-lo > 1 and lo+1 >= 40 and a <= len(profiles[0])-40)
            if min(first, len(profiles[0])-1-b) < strip.MARGIN:
                rejected.append('gap:insufficient_outer_clearance')
            elif any(any(lo < (l+r)/2 < a for l, r, _ in side) for side in detections[1:]):
                rejected.append('gap:intervening_half_run')
            elif not valid_background or any(
                    np.median(sliding_window_view(p[lo+1-40:a+40], 81), axis=1).min() < 20
                    for p in profiles):
                rejected.append('gap:incomplete_or_dim_background')
            else:
                gaps.append(2*(center-pc))
        previous = a, b, center
    return kept, gaps, rejected


def blur_shape(profiles, bg, us):
    norm = profiles[0]/bg
    c, reason, edge = candidate(norm)
    row = dict(blur_other_edge_flag=int(edge))
    if c is None:
        return dict(row, blur_status=reason), None, None
    # R41's fixed observed segment. The broad feature itself must be central,
    # unique and supported in each half; a second deep core/blend is a veto.
    cores = []
    for p in profiles:
        seg = p[c-145:c+146]
        lo, hi = np.median(seg[:15]), np.median(seg[-15:])
        if min(lo, hi) < 20:
            return dict(row, blur_status='dim_blur_wing'), None, None
        x = np.arange(1, 290)
        base = np.interp(x, [7, 283], [lo, hi])
        sm = np.convolve(seg, np.ones(3)/3, 'valid') / base
        bottom = sm[99:190].min()
        mask = sm < (1+bottom)/2
        bounds = np.flatnonzero(np.diff(np.r_[False, mask, False].astype(int))).reshape(-1, 2)
        cores_ = [(a+1, b) for a, b in bounds if b-a >= 3]
        if len(cores_) != 1:
            return dict(row, blur_status='blended_or_no_core'), None, None
        a, b = cores_[0]
        if (bottom >= .88 or not (15 < a < b < 276 and 100 <= (a+b)/2 <= 190)
                or b-a+1 < 6 or np.count_nonzero(seg[a:b+1] < base[a-1:b]*(1+bottom)/2) < 6):
            return dict(row, blur_status='weak_edge_or_narrow_core'), None, None
        cores.append((a, b))
    mids = [np.mean(h) for h in cores]
    if min(mids) < max(a for a, _ in cores) or max(mids) > min(b for _, b in cores):
        return dict(row, blur_status='half_core_mismatch'), None, None
    return dict(row, blur_status='ok'), (us, norm[c-145:c+146]), c-145+mids[0]


def extended_strip(path, roi, us, seen):
    """Same native/duplicate/rail/20 DN checks as strip.short_strip on the new field."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'missing or invalid DNG: {path.name}')
    raw, black, white = strip.read_native(path, us)
    # Keep the original identity region, also used by strip.capture for the CAL
    # exclusions. An extension must not make a repeated central strip independent.
    a, b, l, r = strip.ROI
    key = blake2b(raw[2*a:2*b:2, 2*l:2*r:2].tobytes(), digest_size=16).digest()
    if key in seen:
        raise ValueError(f'{path.name}: duplicate native G1 strip')
    seen.add(key)
    y0, y1, x0, x1 = roi
    patch = raw[2*y0:2*y1, 2*x0:2*x1]
    floor, clip = np.count_nonzero(patch == 0), np.count_nonzero(patch >= white)
    g = patch[::2, ::2].astype(float)-black
    left, right = np.hsplit(g, [g.shape[1]//2])
    full, lo, hi = g.mean(), left.mean(), right.mean()
    gate = 'FAIL_FLOOR' if floor else 'CLIPPED' if clip else 'BELOW_20DN' if min(full, lo, hi) < 20 else 'PASS'
    return g, dict(status=gate, full_g1_dn=full, left_g1_dn=lo, right_g1_dn=hi, clip1=clip, floor1=floor)


def frame(path, roi, us, seen, extended=False):
    if extended:
        g, q = extended_strip(path, roi, us, seen)
    elif roi != strip.ROI:
        raise ValueError('short strip and receipt coordinates differ')
    else:
        g, q = strip.short_strip(path, us, seen)
    parts = [g, *np.hsplit(g, [g.shape[1]//2])]
    profiles = [h.mean(1) for h in parts]
    y0 = roi[0]
    row = dict(status=q['status'], mean_dn=q['full_g1_dn'], left_mean_dn=q['left_g1_dn'],
               right_mean_dn=q['right_g1_dn'], clip_n=q['clip1'], floor_n=q['floor1'])
    if row['status'] != 'PASS':
        return row, None, []
    bg = shade(profiles[0])
    if not np.all(np.isfinite(bg) & (bg > 0)):
        return dict(row, status='invalid_shading'), None, []
    row.update(fine_gate(g, profiles[0], bg))
    gaps = []
    if us != US['1250']:
        kept, gaps, rejected = morphology(parts, profiles, y0)
        row.update(morph_n=len(kept), bounds70_raw_y=';'.join(f'{2*(y0+a)}:{2*(y0+b)}' for a, b, _, _ in kept),
                   centers_raw_y=series(2*(y0+c) for _, _, c, _ in kept), fwhm_raw_rows=[w for _, _, _, w in kept],
                   rejected=';'.join(rejected))
    if row['fine_status'] != 'below_strip_gates':
        return dict(row, blur_status='ambiguous_fine_component'), None, []
    blur, event, c = blur_shape(profiles, bg, us)
    row.update(blur, blur_center_raw_y=2*(y0+c) if c is not None else None)
    if us != US['1250']:
        row.update(broad_n=row['morph_n'], gaps_raw_rows=series(gaps))
    return row, event, gaps


def agree(scales):
    # Inclusive boundary on the R41 0.1-us grid, e.g. 7.6 and 8.4.
    return np.ptp(scales) <= .10*np.mean(scales) + 1e-12


def calibration(events, shorts, long, complete=True):
    """First (larger exposure difference) gives the family scale; second checks it."""
    fits, scales = [], []
    for short in shorts:
        if complete:
            row = fit(events[short], events[long])
            if row['status'] == 'ok' and row['individual_edge_n']:
                row.update(status='skipped_individual_search_edge', effective_us_per_raw_row=None)
        else:
            row = dict(status='incomplete_day_1250_window', short_n=len(events[short]), long_n=len(events[long]), pairs=0)
        fits.append(dict(row, short_us=US[short], long_us=US[long]))
        if row['status'] == 'ok':
            scales.append(row['effective_us_per_raw_row'])
    if not complete:
        return fits, 'incomplete_day_1250_window', None
    if len(scales) != 2:
        return fits, 'too_few_qualified_fits', None
    if not agree(scales):
        return fits, 'disagreeing_shutter_scales', None
    return fits, 'ok', scales[0]


def select_scale(short_status, short_scale, long_status, long_scale):
    both = short_scale is not None and long_scale is not None
    if both and not agree([short_scale, long_scale]):
        return 'disagreeing_calibrations', 'disagree', None, None
    cross = 'agree' if both else 'not_testable'
    if short_scale is not None:
        return 'ok', cross, 'short_200_500', short_scale
    if long_scale is not None:
        return 'ok', cross, 'long_312p5_1250', long_scale
    return (short_status if long_status == 'not_acquired' else 'no_qualified_scale'), cross, None, None


def analyze(paths, strips, states=STATES, extended=False):
    seen = set()
    supplements = {s: {n for ph, n in paths if ph == f'day_{s}_1250'} for s in states}
    if any(supplements.values()):
        # Same native G1 digest as short_strip(): reject a renamed/copied CAL
        # even if the file inode, DAY index or DNG metadata have changed.
        for s in states:
            if supplements[s] and {n for ph, n in paths if ph == f'cal_{s}_4000'} != {1, 2}:
                raise ValueError(f'{s}: missing independent confirm 4000 us CAL pair')
        for path in paths.values():
            cal = strip.CAL.fullmatch(path.name)
            if cal and cal[1] in states:
                strip.capture(path, int(cal[2]), seen, 0)  # identity only; never append a CAL shape
    for state in states:
        cal, roi = strips.get(state, ('MISSING', None))
        common = dict(state=state, strip_status=cal)
        if roi is None:
            yield dict(common, kind='state', status='no_qualified_strip', short_scale_status='no_qualified_strip',
                       long_scale_status='no_qualified_strip', cross_scale_status='not_testable',
                       physical_pwm_hz_status='unidentified')
            continue
        common.update(zip(('y0', 'y1', 'x0', 'x1'), roi))
        events, intervals, frames = {}, [], []
        for token, us in US.items():
            phase = f'day_{state}_{token}'
            events[token] = []
            for (ph, n), path in sorted(paths.items()):
                if ph != phase:
                    continue
                if n < 1:
                    raise ValueError(f'{phase}: nonpositive frame index')
                row, event, gaps = frame(path, roi, us, seen, extended)
                frames.append(dict(common, kind='frame', phase=phase, frame_n=n, exposure_us=us,
                                   frame_role='blur_only' if token == '1250' else 'spacing_and_blur', **row))
                if event is not None:
                    events[token].append(event)
                if gaps:
                    intervals.append(gaps)
        short_fits, ss, short_scale = calibration(events, ('200', '312'), '500')
        long_ids = supplements[state]
        long_fits, ls, long_scale = (calibration(events, ('312', '500'), '1250', long_ids == set(range(1, 7)))
                                     if long_ids else ([], 'not_acquired', None))
        s_gate, cross, source, scale = select_scale(ss, short_scale, ls, long_scale)
        for row in frames:
            widths = row.get('fwhm_raw_rows', [])
            if widths and row.get('broad_n') and scale is not None:
                row.update(apparent_fwhm_us=series(w*scale for w in widths), scale_source=source)
            if 'fwhm_raw_rows' in row:
                row['fwhm_raw_rows'] = series(widths)
            yield row
        for family, rows in [('short', short_fits), ('long', long_fits)]:
            for row in rows:
                yield dict(common, kind='fit', scale_family=family, **row)
        allgaps = [gap for frame_gaps in intervals for gap in frame_gaps]
        g_gate = ('too_few_within_frame_spacings' if len(intervals) < 2 else 'inconsistent_spacings'
                  if np.ptp(allgaps) > .10*np.median(allgaps) else 'ok')
        row = dict(common, kind='state', status=s_gate if s_gate != 'ok' else g_gate,
                   short_scale_status=ss, short_scale_us_per_raw_row=short_scale,
                   day_1250_n=len(long_ids), long_scale_status=ls, long_scale_us_per_raw_row=long_scale,
                   cross_scale_status=cross, scale_status=s_gate, scale_source=source,
                   spacing_status=g_gate, spacing_frames=len(intervals),
                   spacing_n=len(allgaps), physical_pwm_hz_status='unidentified')
        if allgaps:
            row.update(spacing_min_raw_rows=min(allgaps), spacing_max_raw_rows=max(allgaps))
        if g_gate == 'ok':
            row['spacing_median_raw_rows'] = np.median([np.median(gaps) for gaps in intervals])
        if scale is not None:
            row['effective_us_per_raw_row'] = scale
            if g_gate == 'ok':
                row.update(status='conditional', conditional_period_us=row['spacing_median_raw_rows']*scale)
        yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    ap.add_argument('strip', metavar='strip.csv', type=Path)
    ap.add_argument('--extended', action='store_true', help='secondary confirm analysis using extended.py CAL receipts')
    args = ap.parse_args()
    try:
        with args.strip.open(newline='') as f:
            strips = receipts(f, confirm=any(args.frames.glob('day_*_1250__*.dng')), extended=args.extended)
        if args.extended and all(roi is not None for _, roi in strips.values()):
            verify_extended(args.frames, strips)
        paths = inputs(args.frames) if any(roi is not None for _, roi in strips.values()) else {}
        rows = list(analyze(paths, strips, extended=args.extended))
    except (ValueError, OSError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
