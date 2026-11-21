#!/usr/bin/env python3
"""R47: python3 -B compare.py frames.csv windows.csv > compare.csv

Use R44 measure.py frames and receipt-ordered R47 windows.py output. Each
(CAL or DAY, shutter) slot can have its own consecutive A/B/C excursion, in
any slot order, on the same HDR surface and wake epoch. The original complete
leg-major schedule also works. sysfs_bl is status: A <= 16000 < B, C = A.
Each decision is conditional on external field and APL dispatch checks.

Brightness is the mean G1 DN above black of an independent CAL pair per leg
at ONE common shutter: use 1250 us, else 500 us for a clipped primary. If
field.py finds clipping only in its outer guard, --field-clipped-1250 selects
the independent 500 us pairs. A brightness mismatch is not grounds to switch.
Each CAL must be >=20 DN G1 and nonrail on all CFA sites in the fixed ROI.
Require B/A, B/C and C/A mean-DN ratios each within 5% of unity.
The DAY holdout checks the same signal gates on every release at one common
shutter, independent of notch detection; DAY is never a CAL substitute.

At each DAY shutter, R44's depth and FWHM refer to the same qualified G1
event per release. Counts and empirical ranges are descriptive, not confidence
intervals; blank means unmeasured. Depth needs >=3 qualified releases per
leg, A/C median drift <=3 pp, B >=3 pp from BOTH medians in one direction,
and strictly disjoint B ranges. Width is reported separately in RAW rows:
no pp threshold applies to a width, and no time scale is inferred.
"""

import argparse
from collections import defaultdict
import csv
from itertools import groupby
from pathlib import Path
from statistics import fmean
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import compare as r44


LEGS = ('offA', 'offB', 'offC')
SHORT = r44.EXPOSURE_NS
CAL = ('1250', '500')  # primary first, then the independent replacement
EXPOSURES = {'day': SHORT, 'cal': {'1250': 1250000, '500': 500000, '4000': 4000000}}
RAILS = [s+k for s in ('', 'r_', 'g2_', 'b_') for k in ('floor_n', 'clip_n')]
ROI = dict(y0='630', y1='1250', x0='754', x1='799')
WINDOW = dict(r44.HDR, dc_label='off', panel_dc_pre='0', panel_dc_post='0',
              pref_pre='0', pref_post='0', display_power='On', hdr_layer_present='True',
              sdm_tr='16', video_source_ltrb='0 0 720 1584', video_display_ltrb='0 0 1440 3168',
              thermal_status='0', thermal_override='False', brightness_throttling_status='0',
              iso='6400', **{'roi_'+key: val for key, val in ROI.items()})
FRAME = dict(ROI, iso='6400', cfa='GBRG')


def check(row, expected):
    for key, value in expected.items():
        if row[key] != value:
            raise ValueError(f'{row["phase"]}: {key}={row[key]!r}, expected {value!r}')


def bind(frames_csv, windows_csv):
    windows, bl, order, wakes = {}, {}, [], set()
    fields = (*WINDOW, 'phase', 'sysfs_bl', 'wake_epoch', 'exposure_ns', 'frames', 'sf_refresh_hz', 'sdm_fps')
    for w in r44.read_csv(windows_csv, fields):
        p = w['phase']
        parts = p.split('_')
        if len(parts) != 3 or p in windows:
            raise ValueError(f'{p}: unexpected or duplicate window')
        group, leg, token = parts
        exposures = EXPOSURES.get(group, {})
        if leg not in LEGS or token not in exposures:
            raise ValueError(f'{p}: unexpected R47 phase')
        check(w, dict(WINDOW, group=group))
        if not (float(w['sf_refresh_hz']) == float(w['sdm_fps']) == 120
                and int(w['exposure_ns']) == exposures[token]):
            raise ValueError(f'{p}: wrong active HWC/SDM refresh or shutter')
        if group == 'cal' and int(w['frames']) != 2:
            raise ValueError(f'{p}: expected an independent CAL pair')
        level = int(w['sysfs_bl'])
        if bl.setdefault(leg, level) != level:
            raise ValueError(f'{p}: status BL changed within {leg}')
        windows[p] = w
        order.append(((group, token), leg))
        wakes.add(int(w['wake_epoch']))
    if len(wakes) != 1 or min(wakes) <= 0:
        raise ValueError('all slots must share one positive wake epoch')
    shutters = ['125', '200', '312']
    for leg in LEGS:
        for p in [f'cal_{leg}_1250', *(f'day_{leg}_{t}' for t in shutters)]:
            if p not in windows:
                raise ValueError(f'{p}: missing window')
    if any(f'day_{leg}_500' in windows for leg in LEGS):
        shutters.append('500')
    if not (0 < bl['offA'] == bl['offC'] <= 16000 < bl['offB']):
        raise ValueError(f'expected 0 < A = C <= 16000 < B in status BL, got {bl}')

    # Match windows.py: a slot-wise excursion must close before the next A.
    # Simply filtering by shutter would also admit interleaved half-brackets.
    leg_major = tuple(leg for leg, _ in groupby(leg for _, leg in order)) == LEGS
    if not leg_major:
        for slot, block in groupby(order, key=lambda entry: entry[0]):
            if tuple(leg for _, leg in block) != LEGS:
                raise ValueError(f'{slot}: expected consecutive offA/offB/offC windows')
    for group, token in {slot for slot, _ in order}:
        phases = [f'{group}_{leg}_{token}' for leg in LEGS]
        if any(p not in windows for p in phases) or len({int(windows[p]['frames']) for p in phases}) != 1:
            raise ValueError(f'{group}_{token}: missing leg or unequal release counts')

    frames = defaultdict(list)
    fields = (*FRAME, 'phase', 'group', 'scene', 'frame_n', 'exposure_us', 'gate', 'event_status',
              *RAILS, *r44.METRICS)
    for f in r44.read_csv(frames_csv, fields):
        p = f['phase']
        if p not in windows:
            raise ValueError(f'{p}: no bound window')
        group, leg, _ = p.split('_')
        check(f, dict(FRAME, group=group, scene=leg))
        if (min(int(f[k]) for k in RAILS) < 0 or not f['gate'] or not f['event_status']
                or (f['event_status'] == 'ok' and f['gate'] != 'ok')
                or (f['gate'] == 'ok' and (float(f['mean_dn']) < 20
                    or int(f['clip_n']) != 0 or int(f['floor_n']) != 0))):
            raise ValueError(f'{p}/{f["frame_n"]}: inconsistent signal or event gate')
        frames[p].append(f)
    # Also binds indices 1..receipt count and actual exposure for every CAL.
    summaries = {p: r44.summarize(frames[p], w) for p, w in windows.items()}
    return frames, summaries, bl, wakes.pop(), shutters


def signal_status(f):
    if any(int(f[k]) for k in RAILS if k.endswith('floor_n')):
        return 'storage_floor'
    if f['gate'] not in ('ok', 'clipped') or float(f['mean_dn']) < 20:
        return 'unusable_signal'
    return 'clipped' if any(int(f[k]) for k in RAILS if k.endswith('clip_n')) else f['gate']


def calibration(frames, field_clipped_1250):
    result = dict(cal_exposure_us=None, brightness_match='unresolved_no_common_usable_cal')
    means = None
    reference = '1250'
    for token in CAL:  # fixed priority, independent of the differences or DAY metrics
        pairs = [frames.get(f'cal_{leg}_{token}', []) for leg in LEGS]
        statuses = [[signal_status(f) for f in pair] for pair in pairs]
        good = [s.count('ok') for s in statuses]
        result[f'cal_{token}_usable_A_B_C'] = ';'.join(f'{n}/{len(p)}' for n, p in zip(good, pairs))
        if token == '1250':
            gates = {s for group in statuses for s in group}
            if gates <= {'ok', 'clipped'} and (field_clipped_1250 or 'clipped' in gates):
                reference = '500'
        if token == reference and good == [2, 2, 2]:
            means = [fmean(float(f['mean_dn']) for f in pair) for pair in pairs]
            result['cal_exposure_us'] = int(token)
    result['field_clipped_1250_declared'] = field_clipped_1250
    a, b, c = means or (None, None, None)
    diffs = [(x-y)*100/y for x, y in ((b, a), (b, c), (c, a))] if means else (None, None, None)
    result.update(zip(('cal_A_mean_dn', 'cal_B_mean_dn', 'cal_C_mean_dn'), (a, b, c)))
    result.update(zip(('cal_B_vs_A_pct', 'cal_B_vs_C_pct', 'cal_C_vs_A_pct'), diffs))
    if means:
        result['brightness_match'] = ('matched' if max(map(abs, diffs)) <= 5 + 1e-12
                                      else 'confounded_cal_brightness')
    return result


def compare(frames_csv, windows_csv, field_clipped_1250=False):
    frames, summaries, bl, wake, shutters = bind(frames_csv, windows_csv)
    cal = calibration(frames, field_clipped_1250)
    for token in shutters:
        phases = [f'day_{leg}_{token}' for leg in LEGS]
        stats = [summaries[p] for p in phases]
        counts = [ok for ok, _, _ in stats]
        usable = [sum(signal_status(f) == 'ok' for f in frames.get(p, [])) for p in phases]
        held = all(good == n > 0 for good, (_, n, _) in zip(usable, stats))
        for metric in r44.METRICS:
            row = dict(exposure_us=SHORT[token]/1000, metric=metric, wake_epoch=wake)
            ranges = []
            for leg, good, (ok, total, summary) in zip(LEGS, usable, stats):
                row[leg+'_status_bl'] = bl[leg]
                row[leg+'_signal_usable'] = good
                row[leg+'_qualified'], row[leg+'_total'] = ok, total
                ranges.append(summary[metric])
                row.update({leg+'_'+k: v for k, v in zip(('min', 'median', 'max'), summary[metric])})
            a, b, c = ranges
            enough = min(counts) >= 3
            measured = enough or (metric == 'mean_dn' and None not in (a[1], b[1], c[1]))
            row['B_minus_avg_AC_medians'] = b[1]-(a[1]+c[1])/2 if measured else None
            row['day_holdout_signal'] = 'usable' if held else 'unresolved_short_signal'
            row.update(cal)
            row['observed_pattern'] = row['optical_decision'] = None
            if metric == 'depth_pct':
                decision = r44.depth_decision(counts, a, b, c)
                row['observed_pattern'] = {'shallower_on': 'shallower_B', 'deeper_on': 'deeper_B',
                                           'unresolved_off_drift': 'unresolved_AC_return_drift'}.get(decision, decision)
            elif metric == 'fwhm_raw_rows':
                if not enough:
                    pattern = 'unresolved_insufficient_qualified'
                elif b[2] < min(a[0], c[0]):
                    pattern = 'narrower_B_disjoint_ranges'
                elif b[0] > max(a[2], c[2]):
                    pattern = 'wider_B_disjoint_ranges'
                else:
                    pattern = 'unresolved'
                row['observed_pattern'] = pattern
            if row['observed_pattern'] is not None:
                row['optical_decision'] = (cal['brightness_match'] if cal['brightness_match'] != 'matched'
                                           else row['observed_pattern'] if held else row['day_holdout_signal'])
            row['scope'] = 'camera_ROI_only_requires_external_field_and_dispatch'
            yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    ap.add_argument('windows_csv', metavar='windows.csv', type=Path)
    ap.add_argument('--field-clipped-1250', action='store_true',
                    help='external field check rejected CAL/1250 for clipping; require CAL/500 on all legs')
    args = ap.parse_args()
    try:
        rows = list(compare(args.frames_csv, args.windows_csv, args.field_clipped_1250))
    except (ValueError, OSError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
