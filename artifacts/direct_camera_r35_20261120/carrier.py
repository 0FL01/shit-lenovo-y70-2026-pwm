#!/usr/bin/env python3
"""R35: measure a fixed spatial carrier and test its rectangular-exposure response.

Input: sanitized phase__N.dng. Only hRATE_bBL_tLABEL (optionally decorated
with cal/calibration or ret/return) at BL 3600/3601 enters carrier analysis.
RATE and BL describe the window; T always comes from the DNG. Explicit cal
windows take precedence over plain windows for spatial selection; a return
never selects the carrier. linkRATE_bBL_tLABEL is measured at locked k, never
used for calibration or training: the 400/625-us link windows are fresh optical
prediction test in a separate session. Unrecognized phases still get RAW diagnostics.

Frames CSV records spatial selection, unmasked fractional cosine amplitude
and a broad-notch sensitivity check. Both use the same k (cycles across the
740 native Bayer rows), a simultaneous intercept and linear trend, and the
full ROI green mean above black as denominator. No row time is used.

Fit CSV: one group median per (rate, BL, exact DNG duration, mask). Each has
equal weight. Fits use nonnegative A0*abs(sinc(f*T)), sinc(x)=sin(pi*x)/(pi*x),
without a noise pedestal or upper bound on A0. Joint fits share the frequency
hypothesis, with separate A0 per rate. Models use integer Hz. 'holdout' fits
omit the entire test duration at every rate, including returns; 'cv' pools
those predictions. Validation is conditional on the locked spatial carrier,
including the 500-us fold. It is not an independent spatial recalibration.
Frequency is an exposure-response model parameter, not measured PWM Hz.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
import re
import sys

import numpy as np

ARTIFACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACTS / 'direct_camera_r34_20261120'))
from measure import inputs  # validated sanitized paths and unique frame identities
from analyze import read_patch  # R33 decoder / CFA and black-level handling


ROI = (630, 1370, 540, 720)
N = ROI[1] - ROI[0]
Y = (np.arange(N) - (N - 1) / 2) / N
K_GRID = np.arange(80, 321) / 20  # fixed 4..16, step 0.05 cycles/ROI at every rate
ROLE = r'calibration|cal|return|ret'
PHASE = re.compile(rf'(?:(?P<pre>{ROLE})_)?h(?P<h>[1-9]\d*)_b(?P<b>\d+)'
                   rf'_t(?P<t>\d+)(?:_(?P<post>{ROLE}))?')
PICK_RULE = ('b3600_t500; cal else plain; abs(DNG_us-500)<=0.5; no return; '
             'max median Hann-weighted trend+cos amplitude; k=4:0.05:16 cycles/ROI')
AMP_RULE = 'OLS constant+linear+cos+sin at locked k; hypot(cos,sin)/full ROI green mean above black'
MASK_RULE = ('5-row boxcar(edge); deficit>0.20*ROI_mean vs linear interpolation at '
             '+/-1 locked period (one-sided linear extrapolation at ends); '
             'exclude +/-15 Bayer rows; require >=50% rows')
AMPS = {'all_rows': 'amp_frac', 'notch_excluded': 'masked_amp_frac'}


def phase_tags(phase):
    external = phase.startswith('link')
    m = PHASE.fullmatch('h' + phase[4:] if external else phase)
    if not m or (m['pre'] and m['post']) or int(m['b']) not in (3600, 3601):
        return None, None, None, 'other'
    marker = m['pre'] or m['post'] or ''
    role = 'external' if external else 'return' if marker.startswith('ret') else 'cal' if marker else 'plain'
    return int(m['h']), int(m['b']), int(m['t']), role


def read_frames(paths):
    rows, profiles = [], []
    for (phase, n), path in sorted(paths.items()):
        meta, green, clipped, zero = read_patch(path, ROI)
        profile = green.mean(axis=1)
        mean = profile.mean()
        rate, bl, label, role = phase_tags(phase)
        t = meta['exposure_us']
        gate = ('clipped' if clipped else 'mean_below_20' if mean < 20 else
                'invalid_exposure' if not np.isfinite(t) or t <= 0 else 'ok')
        rows.append(dict(phase=phase, frame_n=n, rate_hz=rate, bl=bl, label_us=label,
                         role=role, exposure_us=t, iso=meta['iso'], width=meta['width'],
                         height=meta['height'], focal_mm=meta['focal_length_mm'],
                         orientation=meta['orientation'], roi_bayer_y0_y1_x0_x1='630:1370,540:720',
                         green_mean_dn=mean, raw_green_clip_frac=clipped/(2*green.size),
                         raw_green_zero_frac=zero/(2*green.size), gate=gate,
                         status='other_phase' if role == 'other' else gate,
                         calibration_used=0, calibration_n=0, spatial_selection=PICK_RULE,
                         k_cycles_roi=None, spatial_period_raw_rows=None, k_at_search_edge=None,
                         spatial_amplitude=AMP_RULE, amp_frac=None,
                         notch_mask=MASK_RULE, excluded_roi_rows_lo_hi=None,
                         kept_rows=None, masked_amp_frac=None))
        profiles.append(profile)
    return rows, profiles


def basis(k):
    angle = (2*np.pi*k) * Y
    return np.column_stack((np.ones(N), Y, np.cos(angle), np.sin(angle)))


def amplitude(design, profile, mean):
    coeff = np.linalg.lstsq(design, profile, rcond=None)[0]
    return np.hypot(*coeff[2:]) / mean


def lock_frequency(profiles):
    # Simultaneous linear detrend; taper only the calibration objective. Free
    # phase per capture: do not average shutter phases before fitting.
    p = np.column_stack([v/v.mean() for v in profiles])
    taper = np.sqrt(np.hanning(N))[:, None]
    target = p*taper
    scores = [np.median(np.hypot(*np.linalg.lstsq(basis(k)*taper, target, rcond=None)[0][2:]))
              for k in K_GRID]
    return K_GRID[np.argmax(scores)] if max(scores) > 1e-12 else None


def notch_mask(profile, k):
    """Compare like phases of adjacent fine cycles; a broad deficit can leak into k."""
    p = np.convolve(np.pad(profile, 2, mode='edge'), np.ones(5)/5, 'valid')
    x = np.arange(N)
    lag = N/k
    at = lambda offset: np.interp(x + offset*lag, x, p)
    left, right = at(-1), at(1)
    expected = np.where(x < lag, 2*right - at(2),
                        np.where(x > N-1-lag, 2*left - at(-2), (left + right)/2))
    deep = expected - p > 0.20 * profile.mean()
    return np.convolve(deep.astype(int), np.ones(31, dtype=int), 'same') == 0


def measure(rows, profiles):
    for rate in sorted({r['rate_hz'] for r in rows if r['rate_hz'] is not None}):
        by_rate = [i for i, r in enumerate(rows) if r['rate_hz'] == rate]
        # The name identifies the designated initial window, never its T. A
        # wrong tag in that window or a 500-us miscapture later cannot train k.
        initial = [i for i in by_rate if rows[i]['bl'] == 3600 and rows[i]['label_us'] == 500]
        role = 'cal' if any(rows[i]['role'] == 'cal' for i in initial) else 'plain'
        cal = [i for i in initial if rows[i]['role'] == role and rows[i]['gate'] == 'ok'
               and abs(rows[i]['exposure_us'] - 500) <= 0.5]
        for i in cal:
            rows[i]['calibration_used'] = 1
        k = lock_frequency([profiles[i] for i in cal]) if cal else None
        design = basis(k) if k is not None else None
        for i in by_rate:
            row, p = rows[i], profiles[i]
            row.update(calibration_n=len(cal), k_cycles_roi=k,
                       spatial_period_raw_rows=2*N/k if k is not None else None,
                       k_at_search_edge=int(k in (K_GRID[0], K_GRID[-1])) if k is not None else None)
            if row['gate'] != 'ok':
                continue
            if k is None:
                row['status'] = 'no_usable_500us_calibration' if not cal else 'flat_calibration'
                continue
            keep = notch_mask(p, k)
            # Zero-based half-open ranges relative to ROI start (native Bayer cells).
            edges = np.flatnonzero(np.diff(np.r_[False, ~keep, False].astype(int)))
            row.update(amp_frac=amplitude(design, p, p.mean()), kept_rows=int(keep.sum()),
                       excluded_roi_rows_lo_hi=';'.join(f'{a}:{b}' for a,b in edges.reshape(-1,2)))
            if keep.sum() >= N/2:
                row['masked_amp_frac'] = amplitude(design[keep], p[keep], p.mean())


def duration_groups(rows, column):
    by_key = defaultdict(list)
    for r in rows:
        if r[column] is not None and r['role'] != 'external':
            by_key[r['bl'], r['rate_hz'], r['exposure_us']].append(r)
    for (bl, rate, t), frames in sorted(by_key.items()):
        a = [r[column] for r in frames]
        yield dict(bl=bl, rate_hz=rate, exposure_us=t, n_frames=len(a),
                   phases=';'.join(sorted({r['phase'] for r in frames})),
                   amp_frac=np.median(a), min_amp_frac=min(a), max_amp_frac=max(a))


MODELS = {'best_100_10000': (100, 10000), 'best_100_2000': (100, 2000),
          'best_gt2000': (2001, 10000), '6x_refresh': None,
          'fixed_720': (720, 720), 'fixed_540': (540, 540), 'fixed_864': (864, 864)}


def solve(groups, bounds):
    """Profile out one scale per rate. Equal weight per observed rate/duration."""
    rates = sorted({g['rate_hz'] for g in groups})
    freq = {r: np.arange(bounds[0], bounds[1]+1) if bounds else np.array([6*r]) for r in rates}
    scale, sse = {}, np.zeros(len(freq[rates[0]]))
    for r in rates:
        subset = [g for g in groups if g['rate_hz'] == r]
        amps = np.array([g['amp_frac'] for g in subset])
        t = np.array([g['exposure_us'] for g in subset]) * 1e-6
        transfer = abs(np.sinc(freq[r][:, None] * t))
        denom = np.sum(transfer**2, axis=1)
        # All train durations at numerical sinc zeros: no identifiable scale.
        scale[r] = np.divide(np.sum(transfer*amps, axis=1), denom,
                             out=np.zeros_like(denom), where=denom > 1e-26)
        sse += np.where(denom > 1e-26, np.sum((scale[r][:, None]*transfer - amps)**2, axis=1), np.inf)
    best = np.argmin(sse)
    if not np.isfinite(sse[best]):
        return None
    return {r: (freq[r][best], scale[r][best]) for r in rates}, np.sqrt(sse[best]/len(groups))


def model_rows(groups, scope):
    rates = sorted({g['rate_hz'] for g in groups})
    durations = sorted({g['exposure_us'] for g in groups})
    for name, bounds in MODELS.items():
        base = dict(scope=scope, model=name)
        result = solve(groups, bounds)
        if result is None:
            yield dict(base, kind='fit', status='unidentifiable_scale')
            continue
        params, rmse = result
        for rate, (freq, a0) in params.items():
            yield dict(base, kind='fit', status='ok', rate_hz=rate, model_hz=freq,
                       a0_frac=a0, n_train_groups=len(groups), train_rmse_frac=rmse)

        errors = []
        for t in durations:
            test = [g for g in groups if g['exposure_us'] == t]
            train = [g for g in groups if g['exposure_us'] != t]
            # At least two train durations at each rate for a free-frequency fit;
            # one identifies a fixed-frequency scale unless it lands on a zero.
            need = 2 if bounds and bounds[0] != bounds[1] else 1
            enough = all(sum(g['rate_hz'] == r for g in train) >= need for r in rates)
            result = solve(train, bounds) if enough else None
            for g in test:
                rate = g['rate_hz']
                fold = dict(base, kind='holdout', rate_hz=rate, exposure_us=t,
                            amp_frac=g['amp_frac'], n_train_groups=len(train))
                if result is None:
                    yield dict(fold, status='unidentifiable_scale' if enough else 'too_few_train_durations')
                    continue
                params, rmse = result
                freq, a0 = params[rate]
                pred = a0*abs(np.sinc(freq*t*1e-6))
                error = pred - g['amp_frac']
                errors.append(error)
                yield dict(fold, status='ok', model_hz=freq, a0_frac=a0, train_rmse_frac=rmse,
                           predicted_frac=pred, error_frac=error)
        complete = len(errors) == len(groups)
        yield dict(base, kind='cv', rate_hz=rates[0] if len(rates) == 1 else None,
                   status='ok' if complete else 'incomplete_folds', n_test_groups=len(errors),
                   cv_rmse_frac=np.sqrt(np.mean(np.square(errors))) if complete else None)


FIT_FIELDS = ('kind mask bl scope rate_hz exposure_us phases n_frames amp_frac min_amp_frac '
              'max_amp_frac model model_hz a0_frac n_train_groups train_rmse_frac predicted_frac '
              'error_frac n_test_groups cv_rmse_frac status').split()


def fits(rows):
    for mask, column in AMPS.items():
        groups = list(duration_groups(rows, column))
        for g in groups:
            yield dict(g, kind='group', mask=mask)
        for bl in sorted({g['bl'] for g in groups}):
            joint = []
            for rate in sorted({g['rate_hz'] for g in groups if g['bl'] == bl}):
                subset = [g for g in groups if g['bl'] == bl and g['rate_hz'] == rate]
                if len(subset) < 2:
                    yield dict(kind='fit', scope='per_rate', mask=mask, bl=bl, rate_hz=rate,
                               n_train_groups=len(subset), status='too_few_durations')
                    continue
                joint.extend(subset)
                for r in model_rows(subset, 'per_rate'):
                    yield dict(r, rate_hz=rate, mask=mask, bl=bl)
            if len({g['rate_hz'] for g in joint}) > 1:
                for r in model_rows(joint, 'joint_rates'):
                    yield dict(r, mask=mask, bl=bl)


def write_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: format(v, '.12g') if isinstance(v, float) else v for k,v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', type=Path)
    parser.add_argument('--frames-csv', type=Path, required=True)
    parser.add_argument('--fit-csv', type=Path, required=True)
    args = parser.parse_args()
    try:
        paths = inputs(args.frames)
        outputs = {p.resolve() for p in (args.frames_csv, args.fit_csv)}
        if len(outputs) != 2 or outputs.intersection(p.resolve() for p in paths.values()):
            parser.error('two distinct CSV output paths, separate from the inputs, are required')
        rows, profiles = read_frames(paths)
        measure(rows, profiles)
        write_csv(args.frames_csv, list(rows[0]), rows)
        write_csv(args.fit_csv, FIT_FIELDS, fits(rows))
    except OSError as exc:
        parser.error(exc.strerror)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
