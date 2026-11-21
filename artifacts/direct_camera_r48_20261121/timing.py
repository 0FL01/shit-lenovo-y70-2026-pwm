#!/usr/bin/env python3
"""R48 auxiliary timing: python3 -B timing.py FRAMES > timing.csv

Use one closed epoch on one continuous SDR clip per invocation. An adjacent
acquisition.log is checked for phase/DBV/epoch; standalone FRAMES must be
from the same windows.py-verified archive. windows.py binds the actual DBV
and surface; expected_dbv here is the schedule label. CAL is by code on the
fixed R46 long strip, independently of the primary ROI. Use one CAL shutter
for all four codes (default 312.5 us); shortening can only rescue clipping.
Four distinct releases must cover the guard: at every y one must illuminate
the *whole* row. Each must illuminate >=70% of each quarter with no rails or
lateral intrusion.

DAY A..D, Dr..Ar are eight distinct samples. Bs and Q are held-code controls
at B: spacing only. No cross-position scales, spacings or pooled widths. R46
qualifies full/half-strip morphology, 100-cell outer clearance, light between
events, fine-component rejection and isolated blur shapes. --frames reports
the native widths and the apparent (exposure-integrated) FWHM where qualified.

Only 125/312.5 and 200/312.5 blur fits on four original DAYs per shutter may
qualify a leg. Both fits must pass including individual-edge veto and agree
within 10% (range/mean). All actual same-frame adjacent gaps must agree within
10% (range/median), on >=2 distinct releases. Use the lead gradient times the
median of per-release median gaps. Its reciprocal assumes stationary identical
broad events and constant local phase gradient: it is not physical PWM Hz.
"""

import argparse
import csv
from pathlib import Path
from statistics import median
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.windows import read_windows
from direct_camera_r46_20261121 import strip, timing
from direct_camera_r47_20261121.field import releases
from direct_camera_r47_20261121.longcheck import ROI, SHUTTERS


DBV = dict(zip(('offA', 'offB', 'offC', 'offD'), range(14055, 14059)))
HELD = {'offBs': 'offB', 'offQ': 'offB'}
CAL_STATE = {**{s: s for s in DBV}, **{s+'r': s for s in reversed(DBV)}, **HELD}
CAL_US = {'500': 500., '312': 312.5, '200': 200.}
SUMMARY = ('state expected_dbv cal_state cal_us cal_status day_n_125_200_312 status '
           'spacing_frames spacing_n gaps_raw_rows_by_release spacing_status fit_125_312_status '
           'fit_200_312_status scale_status lead_125_312_us_per_raw_row check_200_312_us_per_raw_row '
           'conditional_period_us conditional_broad_recurrence_hz physical_pwm_hz_status').split()
FRAME = ('state expected_dbv phase frame_n exposure_us status fine_status morph_n broad_n '
         'centers_raw_y fwhm_raw_rows apparent_fwhm_us gaps_raw_rows rejected blur_status').split()


def qualify(frames, state, token, seen, n=4):
    """R46 field/guard on n independent CALs; no vertical or cross-release pixel fill."""
    try:
        paths = releases(frames, f'cal_{state}_{token}')
        if set(paths) != set(range(1, n+1)):
            return 'incomplete_CAL'
        caps = [strip.capture(path, CAL_US[token], seen, strip.GUARD) for path in paths.values()]
    except ValueError as exc:
        return f'invalid_CAL:{exc}'
    if any(floor for _, _, floor in caps):
        return 'floor_CAL'
    if any(clip for _, clip, _ in caps):
        return 'clipped_CAL'
    levels = [strip.levels(g) for g, _, _ in caps]
    if any(lateral.any() for _, lateral, _ in levels):
        return 'lateral_intrusion_CAL'
    lit = np.stack([score.min(axis=1) >= 1 for score, _, _ in levels])
    if not lit.any(axis=0).all():
        return 'uncovered_rows_CAL'
    if any(q.mean(axis=1).min() < .70 for q in np.array_split(lit, 4, axis=1)):
        return 'insufficient_quarter_support_CAL'
    return 'PASS'


def measure(frames, state, field_status, seen, *, held=False):
    events = {t: [] for t in SHUTTERS}
    paths = {t: releases(frames, f'day_{state}_{t}') for t in SHUTTERS}
    required = ('125',) if held else tuple(SHUTTERS)
    if held and any(paths[t] for t in ('200', '312')):
        raise ValueError(f'{state}: unexpected non-125 DAY for a sham control')
    complete = all(set(paths[t]) == {1, 2, 3, 4} for t in required)
    row = dict(state=state, day_n_125_200_312='/'.join(str(len(p)) for p in paths.values()),
               physical_pwm_hz_status='unidentified_carrier', status='incomplete',
               scale_status='no_qualified_long_CAL', spacing_status='no_qualified_long_CAL')
    details, intervals = [], {}
    if field_status != 'PASS':
        return row, details  # unmeasured spacing counts stay blank

    for token, us in SHUTTERS.items():
        phase = f'day_{state}_{token}'
        for n, path in paths[token].items():
            if n > 4:
                raise ValueError(f'{phase}: unexpected release __{n}')
            r, event, gaps = timing.frame(path, ROI, us, seen)
            # R46 retains ambiguous morphology in its diagnostics; never convert
            # those widths into apparent times or count those intervals as gaps.
            details.append(dict(r, state=state, phase=phase, frame_n=n, exposure_us=us))
            if event is not None and not held:
                events[token].append(event)
            if gaps:
                intervals[f'{token}#{n}'] = gaps

    gaps = [gap for group in intervals.values() for gap in group]
    spacing = ('too_few_releases_with_gaps' if len(intervals) < 2 else
               'inconsistent_gaps' if max(gaps)-min(gaps) > .10*median(gaps) else 'ok')
    row.update(spacing_frames=len(intervals), spacing_n=len(gaps), spacing_status=spacing,
               gaps_raw_rows_by_release=';'.join(f'{key}:{timing.series(v)}' for key, v in intervals.items()))
    scale = None
    if not complete:
        row['scale_status'] = 'incomplete_DAY:' + '+'.join(t for t in required if len(paths[t]) != 4)
    elif held:
        row.update(status='spatial_only', scale_status='125_only_sham')
    else:
        scales = []
        for token in ('125', '200'):
            fit = timing.fit(events[token], events['312'])
            status = fit['status']
            if status == 'ok':
                if fit['individual_edge_n']:
                    status = 'skipped_individual_search_edge'
                else:
                    gradient = fit['effective_us_per_raw_row']
                    row[('lead' if token == '125' else 'check')+f'_{token}_312_us_per_raw_row'] = gradient
                    scales.append(gradient)
            row[f'fit_{token}_312_status'] = status
        scale_status = ('too_few_qualified_fits' if len(scales) != 2 else
                        'disagreeing_shutter_scales' if not timing.agree(scales) else 'ok')
        row.update(scale_status=scale_status, status='unresolved')
        if scale_status == 'ok':
            scale = scales[0]
            if spacing == 'ok':
                period = scale * median(map(median, intervals.values()))
                row.update(status='conditional', conditional_period_us=period,
                           conditional_broad_recurrence_hz=1e6/period)

    for r in details:
        widths = r.get('fwhm_raw_rows', [])
        if r.get('broad_n') and scale is not None:
            r['apparent_fwhm_us'] = timing.series(w*scale for w in widths)
        r['fwhm_raw_rows'] = timing.series(widths)
    return row, details


def check_archive(frames):
    log = frames.parent / 'acquisition.log'
    if not log.exists() and not log.is_symlink():
        return
    windows = list(read_windows(log))
    if len({w[-2] for w in windows}) != 1:
        raise ValueError('timing archive spans multiple wake epochs')
    originals = set()
    for phase, scene, bl, hwc, hz, ns, _, sizes in windows:
        group, state, token = phase.split('_')
        shutters = {**SHUTTERS, **CAL_US} if group == 'cal' else SHUTTERS
        states = DBV if group == 'cal' else CAL_STATE
        if (group not in ('day', 'cal') or state not in states or token not in shutters or
                (scene, bl, hwc, hz, ns) != ('sdr', DBV[CAL_STATE[state]], 0, 120, shutters[token]*1000)):
            raise ValueError(f'{phase}: window disagrees with R48 level, scene, refresh or shutter')
        originals.update(f'{phase}__{i}.dng' for i in range(1, len(sizes)+1))
    actual = {p.name for p in frames.iterdir() if p.suffix.lower() in ('.dng', '.partial')}
    if originals != actual:
        raise ValueError('FRAMES does not match the closed acquisition windows')


def analyze(frames, token):
    if strip.ROI != ROI or strip.GUARD != 20 or strip.MARGIN != 100:
        raise ValueError('frozen R46 long strip, CAL guard or spacing margin changed')
    if not frames.is_dir():
        raise ValueError('FRAMES must be one epoch directory')
    check_archive(frames)
    seen = set()  # shared native G1 identity check across CAL, DAY, legs and shutters
    # Keep every acquired CAL out of DAY (including an unselected shorter
    # bracket). A shorter CAL cannot bypass poor/lost field coverage, missing
    # releases, or a rail at the floor on an acquired longer bracket.
    veto = []
    for other, us in {**CAL_US, '125': 125.}.items():
        if other == token or not any(frames.glob(f'cal_*_{other}__*')):
            continue
        if us > CAL_US[token]:
            primary = {s: qualify(frames, s, other, seen) for s in DBV}
            veto.extend(f'{s}/{other}:{v}' for s, v in primary.items() if v not in ('PASS', 'clipped_CAL'))
            if all(v == 'PASS' for v in primary.values()):
                veto.append(f'longer_{other}_passed_use_that_bracket')
        else:
            for s in DBV:
                for path in releases(frames, f'cal_{s}_{other}').values():
                    strip.capture(path, us, seen, 0)
    fields = {s: qualify(frames, s, token, seen) for s in DBV}
    failed = ','.join(s for s, status in fields.items() if status != 'PASS')
    states, details = [], []
    for state, cal in CAL_STATE.items():
        status = fields[cal]
        if status == 'PASS':
            if failed:
                status = 'blocked_other_CAL:' + failed
            elif veto:
                status = 'blocked_replacement_CAL:' + ','.join(veto)
        row, frames_out = measure(frames, state, status, seen, held=state in HELD)
        row.update(expected_dbv=DBV[cal], cal_state=cal, cal_us=CAL_US[token], cal_status=status)
        states.append(row)
        details.extend(dict(r, expected_dbv=DBV[cal]) for r in frames_out)
    return states, details


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    ap.add_argument('--cal-us', choices=('312', '312.5', '500', '200'), default='312',
                    help='one common four-release CAL shutter (default: 312.5)')
    ap.add_argument('--frames', dest='details', action='store_true', help='emit per-DAY diagnostics instead of states')
    args = ap.parse_args()
    try:
        states, details = analyze(args.frames, '312' if args.cal_us == '312.5' else args.cal_us)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    fields, rows = (FRAME, details) if args.details else (SUMMARY, states)
    out = csv.DictWriter(sys.stdout, fields, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v
                      for k in fields if (v := row.get(k)) is not None})


if __name__ == '__main__':
    main()
