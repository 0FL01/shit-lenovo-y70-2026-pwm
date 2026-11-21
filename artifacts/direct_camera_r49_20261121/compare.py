#!/usr/bin/env python3
"""R49: python3 -B compare.py frames.csv > compare.csv

Use the main archive's R43/R48 measure.py output: cal_{A,B,R}_25000 for the
common brightness calibration; day_{A,B,R}_{1250,4000,6667} for contrast.
Optional --field field.csv binds the independent R49 25-ms CAL guard checks.
Without it, valid camera metrics are descriptive and field qualification is
explicitly outstanding. A failed CAL withholds band metrics for that visit.
Original independence, visit order and state need separate acquisition receipts.

G1 mean DN includes every non-clipped shot, even below the signal gate. Net DN
is blank unless same-visit black_{A,B,R}_TOKEN (or dark_) windows are provided
at that shutter. For the separate stock archive use:
  python3 -B compare.py --stock-context stock_frames.csv > stock_levels.csv
This reports only cal_S_25000 (minus dark_S_25000 if usable) and day_S_4000;
neither the stock dark nor a stock level enters a main contrast.
Matching requires clean CALs, >=3 shots per visit and signed B/A, B/R and R/A
within ±5% on gross CAL light, and on net CAL light if CAL darks are supplied.
An unmatched B light level is reported independently of the band decision:
R must return within 5%, and B must differ by >5% from A and R with disjoint
shot ranges (on both gross and net scales when darks are available).
Row P01 dip uses signal-qualified shots; depth uses only qualified local events.
A reversible contrast requires >=3 valid values per visit, R median within
3 pp of A, and the entire B range >=3 pp beyond BOTH reference ranges in the
same direction. A railed DAY shot cannot contribute a band measurement, and
a partly railed window cannot support a reversible band decision. Numerical
differences from the remaining valid shots are descriptive if the gate fails.
Blank means unmeasured. DN is a camera light calibration, not luminance;
exposure_us is integration time, not a physical notch duration or PWM period.
"""

import argparse
from collections import defaultdict
import csv
from math import isfinite
from pathlib import Path
from statistics import fmean, median
import sys


LEGS = ('A', 'B', 'R')
PAIRS = (('B', 'A'), ('B', 'R'), ('R', 'A'))
DAY = ('1250', '4000', '6667')
CAL = '25000'
US = {'1250': 1250, '4000': 4000, '6667': 6666.667, CAL: 25000}
SETUP = ('iso', 'y0', 'y1', 'x0', 'x1', 'width', 'height', 'orientation', 'cfa', 'focal_mm', 'white_dn')
METRICS = ('row_p01_dip_pct', 'depth_pct')
FIELDS = ('phase', 'group', 'scene', 'frame_n', 'exposure_us', 'gate', 'event_status',
          'clip_n', 'floor_n', 'mean_dn', *SETUP, *METRICS)
EPS = 1e-10  # roundoff at inclusive decision boundaries


def number(row, key):
    v = float(row[key])
    if not isfinite(v):
        raise ValueError(f'{row["phase"]}: nonfinite {key}')
    return v


def read_frames(path, stock=False):
    windows = defaultdict(dict)
    exposures, setup = {}, None
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames or []
        if len(set(header)) != len(header) or not set(FIELDS) <= set(header):
            raise ValueError('frames.csv: missing R43/R48 measurement columns or duplicate header')
        for r in reader:
            if None in r or None in r.values():
                raise ValueError(f'frames.csv:{reader.line_num}: malformed row')
            if stock and r['phase'] not in ('cal_S_25000', 'dark_S_25000', 'day_S_4000'):
                continue  # select only the prespecified stock controls, never the active diagnostic
            group, leg, token = r['phase'].split('_')
            dark = group in ('black', 'dark')
            if ([group, leg] != [r['group'], r['scene']] or leg not in (('S',) if stock else LEGS) or token not in US or
                    not (dark or (group == 'cal' and token == CAL) or (group == 'day' and token in DAY))):
                raise ValueError(f'{r["phase"]}: unexpected label/group/scene')
            config = tuple(r[k] for k in SETUP)
            setup = config if setup is None else setup
            us = number(r, 'exposure_us')
            if (not all(config) or config != setup or abs(us - US[token]) > .001 or
                    exposures.setdefault(token, us) != us):
                raise ValueError(f'{r["phase"]}: camera setup or tagged exposure mismatch')
            window = windows[token, 'dark' if dark else group, leg]
            n = int(r['frame_n'])
            if n < 1 or n in window or (window and next(iter(window.values()))['phase'] != r['phase']):
                raise ValueError(f'{r["phase"]}/{n}: duplicate release, ambiguous dark or invalid index')
            for k in ('clip_n', 'floor_n'):
                r[k] = int(r[k])
            gate, event = r['gate'], r['event_status']
            if (min(r['clip_n'], r['floor_n']) < 0 or not gate or not event or
                    bool(r['clip_n']) != (gate == 'clipped') or
                    (not r['clip_n'] and bool(r['floor_n']) != (gate == 'storage_floor')) or
                    (event == 'ok' and gate != 'ok')):
                raise ValueError(f'{r["phase"]}/{n}: inconsistent gates or rail counts')
            r['mean_dn'] = number(r, 'mean_dn')
            for k in METRICS:
                valid = gate == 'ok' and (k != 'depth_pct' or event == 'ok')
                r[k] = number(r, k) if valid and r[k] != '' else None
            window[n] = r
    if not any(kind != 'dark' for _, kind, _ in windows):
        raise ValueError('no requested CAL or DAY windows')
    return windows, exposures, dict(zip(SETUP, setup))


def light(rows):
    """Return the gross mean (including low-signal shots) and all non-clipped shots."""
    keep = [r for r in rows if not r['clip_n']]
    return (fmean(r['mean_dn'] for r in keep) if keep else None), keep


def visit_light(windows, kind, token, leg):
    shots = windows.get((token, kind, leg), {}).values()
    dark = windows.get((token, 'dark', leg), {}).values()
    gross, lit = light(shots)
    bg, blacks = light(dark)
    dark_ok = len(dark) == len(blacks) >= 3 and not any(r['floor_n'] for r in blacks)
    net = gross - bg if gross is not None and dark_ok else None
    return dict(total=len(shots), nonclipped=len(lit), railed=sum(bool(r['clip_n'] or r['floor_n']) for r in shots), mean_dn=gross,
                min_mean_dn=min((r['mean_dn'] for r in lit), default=None),
                max_mean_dn=max((r['mean_dn'] for r in lit), default=None),
                signal_ok=len(lit) == len(shots) >= 3 and all(r['gate'] == 'ok' for r in lit),
                dark_total=len(dark), dark_nonclipped=len(blacks), dark_mean_dn=bg, net_mean_dn=net,
                min_net_dn=min(r['mean_dn'] for r in lit) - max(b['mean_dn'] for b in blacks)
                if lit and dark_ok else None,
                max_net_dn=max(r['mean_dn'] for r in lit) - min(b['mean_dn'] for b in blacks)
                if lit and dark_ok else None)


def field_status(path, windows, setup):
    if path is None:
        return dict.fromkeys(LEGS, 'NOT_CHECKED')
    status, quarters = {}, defaultdict(set)
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        required = ('phase', 'scene', 'quarter', 'status', 'state_status', 'exposure_us', 'expected_dbv',
                    'guard', 'n_required', 'n_present', 'required_orientation', 'y0', 'y1', 'x0', 'x1')
        header = reader.fieldnames or []
        if len(set(header)) != len(header) or not set(required) <= set(header):
            raise ValueError(f'{path.name}: missing field.py columns or duplicate header')
        for r in reader:
            s, q, state = r['scene'], r['quarter'], r['state_status']
            if (None in r or None in r.values() or s not in LEGS or r['phase'] != f'cal_{s}_{CAL}' or not state or
                    int(r['expected_dbv']) != 512 or int(r['guard']) != 20 or
                    float(r['exposure_us']) != US[CAL] or r['required_orientation'] != setup['orientation'] or
                    any(r[k] != setup[k] for k in ('y0', 'y1', 'x0', 'x1')) or
                    status.setdefault(s, state) != state or q in quarters[s]):
                raise ValueError(f'{path.name}: unbound or inconsistent field row: {r["phase"]}')
            quarters[s].add(q)
            if state == 'PASS':
                frames = windows.get((CAL, 'cal', s), {})
                n = int(r['n_required'])
                if (r['status'] != 'PASS' or q not in ('1', '2', '3', '4') or
                        not 3 <= n <= 4 or int(r['n_present']) != n or set(frames) != set(range(1, n+1)) or
                        any(int(r[f'clip{i}']) or int(r[f'floor{i}']) or
                            abs(number(r, f'g1_mean_dn{i}') - f['mean_dn']) > 1e-5 for i, f in frames.items())):
                    raise ValueError(f'{r["phase"]}: PASS does not bind the measured CAL releases')
    return {s: ('MISSING_FIELD' if s not in status or (status[s] == 'PASS' and len(quarters[s]) != 4)
                else status[s]) for s in LEGS}


def level_decision(cal, row, dark):
    if row['brightness_match'].startswith('unresolved'):
        return row['brightness_match']
    if any(row[f'cal_{s}_field'] != 'PASS' for s in LEGS):
        return 'unresolved_field_not_checked'
    levels = [('gross', 'min_mean_dn', 'max_mean_dn')]
    if dark:
        levels.append(('net', 'min_net_dn', 'max_net_dn'))
    if any(abs(row[f'cal_{k}_R_vs_A_pct']) > 5 + EPS for k, _, _ in levels):
        return 'unresolved_return_light_drift'
    if row['brightness_match'] == 'matched':
        return 'within_5pct'
    if all(row[f'cal_{k}_B_vs_{s}_pct'] > 5 + EPS and cal['B'][lo] > cal[s][hi]
           for k, lo, hi in levels for s in ('A', 'R')):
        return 'reversible_brighter_B'
    if all(row[f'cal_{k}_B_vs_{s}_pct'] < -5 - EPS and cal['B'][hi] < cal[s][lo]
           for k, lo, hi in levels for s in ('A', 'R')):
        return 'reversible_dimmer_B'
    return 'unresolved_light_range_separation'


def calibration(windows, field):
    cal = {s: visit_light(windows, 'cal', CAL, s) for s in LEGS}
    dark = any(v['dark_total'] for v in cal.values())
    row = dict(cal_exposure_us=US[CAL], brightness_basis='gross_and_net' if dark else 'gross_only')
    for s, v in cal.items():
        row.update({f'cal_{s}_{k}': x for k, x in v.items()})
        row[f'cal_{s}_field'] = field[s]
    matched = True
    for basis, key in (('gross', 'mean_dn'), ('net', 'net_mean_dn')):
        for i, j in PAIRS:
            x, y = cal[i][key], cal[j][key]
            delta = x - y if x is not None and y is not None else None
            pct = 100 * delta / y if delta is not None and y > 0 else None
            row[f'cal_{basis}_{i}_minus_{j}_dn'] = delta
            row[f'cal_{basis}_{i}_vs_{j}_pct'] = pct
            if basis == 'gross' or dark:
                matched &= pct is not None and abs(pct) <= 5 + EPS
    if not all(v['signal_ok'] for v in cal.values()):
        match = 'unresolved_cal_signal'
    elif any(status not in ('PASS', 'NOT_CHECKED') for status in field.values()):
        match = 'unresolved_cal_field'
    elif dark and not all(v['net_mean_dn'] is not None and v['min_mean_dn'] - v['dark_mean_dn'] >= 20
                          for v in cal.values()):
        match = 'unresolved_cal_dark'
    else:
        match = 'matched' if matched else 'outside_5pct'
    row['brightness_match'] = match
    row['level_decision'] = level_decision(cal, row, dark)
    return row, {s: v['signal_ok'] and field[s] in ('PASS', 'NOT_CHECKED') for s, v in cal.items()}


def contrast(windows, token, metric, row, band_ok):
    values = {}
    for leg in LEGS:
        v = [r[metric] for r in windows.get((token, 'day', leg), {}).values()
             if band_ok[leg] and r[metric] is not None]
        values[leg] = v
        row.update({f'{leg}_qualified': len(v), f'{leg}_min': min(v, default=None),
                    f'{leg}_median': median(v) if v else None, f'{leg}_max': max(v, default=None)})
    for i, j in PAIRS:
        x, y = values[i], values[j]
        row[f'{i}_minus_{j}_pp'] = median(x) - median(y) if x and y else None
        # Full empirical interval of x-y; no pairing of arbitrary shot numbers.
        row[f'{i}_minus_{j}_min_pp'] = min(x) - max(y) if x and y else None
        row[f'{i}_minus_{j}_max_pp'] = max(x) - min(y) if x and y else None

    if min(len(values['R']), len(values['A'])) < 3:
        ret = 'unresolved_return_count'
    elif abs(row['R_minus_A_pp']) > 3 + EPS:
        ret = 'unresolved_return_drift'
    else:
        ret = 'within_3pp'
    row['return_status'] = ret
    if not all(band_ok.values()):
        decision = 'unresolved_cal_or_field'
    elif any(row[f'day_{s}_railed'] for s in LEGS):
        decision = 'unresolved_day_rail'
    elif min(map(len, values.values())) < 3:
        decision = 'unresolved_insufficient_qualified'
    elif row['brightness_match'] != 'matched':
        decision = 'unresolved_' + row['brightness_match'].removeprefix('unresolved_')
    elif ret != 'within_3pp':
        decision = ret
    elif any(row[f'cal_{s}_field'] != 'PASS' for s in LEGS):
        decision = 'unresolved_field_not_checked'
    elif min(row['B_minus_A_min_pp'], row['B_minus_R_min_pp']) >= 3 - EPS:
        decision = 'reversible_deeper_B'
    elif max(row['B_minus_A_max_pp'], row['B_minus_R_max_pp']) <= -3 + EPS:
        decision = 'reversible_shallower_B'
    else:
        decision = 'unresolved_no_3pp_range_separation'
    row['decision'] = decision


def compare(path, field_path):
    windows, exposures, setup = read_frames(path)
    cal, band_ok = calibration(windows, field_status(field_path, windows, setup))
    for t in DAY:
        base = dict(token=t, exposure_us=exposures.get(t), **setup, physical_time_status='unresolved', **cal)
        for s in LEGS:
            v = visit_light(windows, 'day', t, s)
            base.update({f'day_{s}_{k}': x for k, x in v.items()})
        for metric in METRICS:
            row = dict(base, metric=metric)
            contrast(windows, t, metric, row, band_ok)
            yield row


def stock_context(path):
    windows, exposures, setup = read_frames(path, stock=True)
    for kind, t in (('cal', CAL), ('day', '4000')):
        v = visit_light(windows, kind, t, 'S')
        yield dict(role='stock_context_only', phase=f'{kind}_S_{t}', exposure_us=exposures.get(t),
                   **setup, **v, physical_time_status='unresolved')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='frames.csv')
    options = ap.add_mutually_exclusive_group()
    options.add_argument('--field', type=Path, metavar='field.csv', help='R49 field.py report for these CALs')
    options.add_argument('--stock-context', action='store_true', help='levels only, from separate stock frames.csv')
    args = ap.parse_args()
    try:
        rows = list(stock_context(args.frames) if args.stock_context else compare(args.frames, args.field))
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
