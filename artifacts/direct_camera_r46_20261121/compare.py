#!/usr/bin/env python3
"""R46: python3 -B compare.py frames.csv windows.csv > compare.csv

Use R44 measure.py and R46 windows.py on the same archive. The latter binds
native frames to chronological receipts and verifies the sole full-field PQ
layer at both boundaries; the snapshots do not prove uninterrupted playback.

At each DAY exposure, R44 summarizes qualified fixed-ROI G1 events only
(mean_dn uses all frames). A blank range is unmeasured. A depth effect needs
>=3 qualified events per leg, <=3 pp return drift, >=3 pp separation from
both 120 Hz medians, and disjoint ranges. These are camera notch depths at
that integration. FWHM is in RAW rows: comparing widths as time across
refresh modes requires independent timing calibration in each mode.

Brightness uses independent CAL/1250 frame means above black, averaged per
leg. Require a usable CAL pair per leg, no failed CAL signal gates, and
|B/A-1|, |B/C-1|, |C/A-1| <= 5%.
On failure, retain measurements and the observed depth pattern but label
the comparison confounded. Neither BL nor short-exposure means can qualify it.
"""

import argparse
from collections import defaultdict
import csv
from itertools import groupby
from math import isclose
from pathlib import Path
from statistics import fmean
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import compare as r44


MODES = {'on120A': (0, 120), 'on144B': (1, 144), 'on120C': (0, 120)}
SHUTTERS = ('200', '312', '500')
REQUIRED = {('day', t) for t in SHUTTERS} | {('cal', '1250')}
ROI = dict(y0='630', y1='1250', x0='754', x1='799')  # R42 half-open Bayer cells
COMMON = dict(r44.HDR, sysfs_bl='3593', dc_label='on', panel_dc_pre='1', panel_dc_post='1',
              pref_pre='1', pref_post='1', display_power='On', hdr_layer_present='True',
              sdm_tr='16', video_source_ltrb='0 0 720 1584', video_display_ltrb='0 0 1440 3168',
              bracket_status='BOUND_120_144_120_AT_BOUNDARIES')
WINDOW_FIELDS = (*COMMON, 'phase', 'refresh_leg', 'sf_refresh_hz', 'sdm_fps', 'wake_epoch',
                 'exposure_ns', 'frames')
FRAME_FIELDS = ('phase', 'group', 'scene', 'frame_n', 'exposure_us', 'gate', 'event_status',
                'iso', 'cfa', *ROI, *r44.METRICS)


def check_fields(row, expected):
    for key, value in expected.items():
        if row[key] != value:
            raise ValueError(f'{row["phase"]}: {key}={row[key]!r}, expected {value!r}')


def bind(frames_csv, windows_csv):
    windows, inventory = {}, defaultdict(set)
    order, wakes = [], set()
    for w in r44.read_csv(windows_csv, WINDOW_FIELDS):  # receipt order, not filename order
        phase = w['phase']
        group, leg, token = phase.split('_')
        if (leg not in MODES or group not in ('cal', 'day') or not token.isdecimal()
                or (group == 'cal' and token not in ('1250', '4000')) or phase in windows):
            raise ValueError(f'{phase}: unexpected or duplicate window')
        hwc, hz = MODES[leg]
        check_fields(w, dict(COMMON, group=group, refresh_leg=leg, hwc_id=str(hwc), sdm_config=str(hwc)))
        if not float(w['sf_refresh_hz']) == float(w['sdm_fps']) == hz:
            raise ValueError(f'{phase}: expected actual SF and SDM refresh {hz}')
        if (group, token) in REQUIRED or group == 'cal':
            ns = int(token)*1000 if group == 'cal' else r44.EXPOSURE_NS[token]
            if int(w['exposure_ns']) != ns:
                raise ValueError(f'{phase}: expected {ns} ns')
        inventory[leg].add((group, token))
        windows[phase] = w
        wakes.add(int(w['wake_epoch']))
        order.append(leg)
    if [k for k, _ in groupby(order)] != list(MODES) or len(wakes) != 1 or min(wakes) <= 0:
        raise ValueError('expected one chronological 120A/144B/120C cycle in one positive wake epoch')
    for leg, found in inventory.items():
        if not REQUIRED <= found or found != inventory['on120A']:
            raise ValueError(f'{leg}: missing CAL/DAY windows or unequal shutter inventories')

    frames = defaultdict(list)
    for f in r44.read_csv(frames_csv, FRAME_FIELDS):
        p = f['phase']
        if p not in windows:
            raise ValueError(f'{p}: no verified window')
        w = windows[p]
        check_fields(f, dict(ROI, iso='6400', cfa='GBRG', group=w['group'], scene=w['refresh_leg']))
        if not f['event_status'] or (f['event_status'] == 'ok' and f['gate'] != 'ok'):
            raise ValueError(f'{p}/{f["frame_n"]}: missing status or inconsistent event gate')
        frames[p].append(f)
    # Checks exposure, frame index inventory and finite measurements, including
    # CAL and any supplementary DAY shutters present in the receipt inventory.
    stats = {p: r44.summarize(frames[p], w) for p, w in windows.items()}
    return frames, stats, wakes.pop()


def calibration(frames):
    result, means = {}, {}
    all_usable = True
    for leg in MODES:
        rows = frames[f'cal_{leg}_1250']
        means[leg] = fmean(float(f['mean_dn']) for f in rows)
        ok = sum(f['gate'] == 'ok' for f in rows)
        result.update({f'cal_{leg}_mean_dn': means[leg], f'cal_{leg}_usable': ok,
                       f'cal_{leg}_total': len(rows)})
        all_usable = all_usable and ok == len(rows) >= 2 and means[leg] > 0
    a, b, c = (means[leg] for leg in MODES)
    diffs = [(x-y)*100/y if y > 0 else None for x, y in ((b, a), (b, c), (c, a))]
    result.update(zip(('cal_B_vs_A_pct', 'cal_B_vs_C_pct', 'cal_C_vs_A_pct'), diffs))
    # Include exactly +/-5%, allowing only floating-point roundoff at the boundary.
    if not all_usable:
        result['brightness_match'] = 'confounded_cal_signal'
    elif all(abs(d) <= 5 or isclose(abs(d), 5, rel_tol=0, abs_tol=1e-12) for d in diffs):
        result['brightness_match'] = 'matched'
    else:
        result['brightness_match'] = 'confounded_cal_brightness'
    return result


DEPTH_LABELS = {'shallower_on': 'shallower_144B', 'deeper_on': 'deeper_144B',
                'unresolved_off_drift': 'unresolved_120_return_drift'}


def compare(frames_csv, windows_csv):
    frames, summaries, wake = bind(frames_csv, windows_csv)
    cal = calibration(frames)
    for token in SHUTTERS:
        for metric in r44.METRICS:
            row = dict(exposure_us=r44.EXPOSURE_NS[token]/1000, metric=metric, wake_epoch=wake, sysfs_bl=3593)
            ranges, counts = [], []
            for leg in MODES:
                phase = f'day_{leg}_{token}'
                ok, n, summary = summaries[phase]
                values = summary[metric]
                row[leg+'_qualified'], row[leg+'_total'] = ok, n
                row.update({leg+'_'+key: v for key, v in zip(('min', 'median', 'max'), values)})
                counts.append(ok)
                ranges.append(values)
            a, b, c = (v[1] for v in ranges)
            row['B_minus_avg_120_medians'] = b-(a+c)/2 if None not in (a, b, c) else None
            row.update(cal)
            row['observed_depth_pattern'] = row['depth_decision'] = None
            if metric == 'depth_pct':
                raw = r44.depth_decision(counts, *ranges)
                pattern = DEPTH_LABELS.get(raw, raw)
                row['observed_depth_pattern'] = pattern
                row['depth_decision'] = pattern if cal['brightness_match'] == 'matched' else cal['brightness_match']
            row['width_note'] = ('RAW rows only; comparing time across refresh requires independent calibration per mode'
                                 if metric == 'fwhm_raw_rows' else None)
            yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    ap.add_argument('windows_csv', metavar='windows.csv', type=Path)
    args = ap.parse_args()
    try:
        rows = list(compare(args.frames_csv, args.windows_csv))
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
