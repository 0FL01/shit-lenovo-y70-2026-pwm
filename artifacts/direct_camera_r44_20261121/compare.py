#!/usr/bin/env python3
"""R44: python compare.py frames.csv windows.csv > compare.csv

Compare stock OFF / ON / returned OFF at each shutter separately. Use the
boundary-verified output of R44 windows.py. High 312.5 us is primary; 200 us
is corroboration. Low-field exposures are exploratory and may lack signal.
Depth, Michelson and FWHM use qualified events; mean_dn uses all frames.
Missing events are not zero-depth measurements. Signed differences are ON
minus the average of the two OFF medians, in the metric's native units.

R43's six same-HDR/30 frames per shutter spanned 2.77 pp at 312.5 us and
2.45 pp at 200 us. These are empirical ranges, not confidence intervals.
Decisions concern camera notch depth at the indicated integration only;
they do not establish physical modulation frequency or continuous emission.
"""

import argparse
from collections import defaultdict
import csv
from math import isfinite
from pathlib import Path
from statistics import median
import sys


STATES = ('off', 'on', 'ret')
METRICS = ('depth_pct', 'michelson_pct', 'fwhm_raw_rows', 'mean_dn')
EXPOSURE_NS = {'125': 125000, '200': 200000, '312': 312500, '500': 500000}
HDR = dict(group='day', scene='hdr', video_dataspace='0x11c60000', sdm_eotf='PQ',
           hwc_dynamic_range='HDR', sdm_dynamic_range='HDR', hdr_mode='HBM_HDR',
           hbm_mode='hdr', session_status='inactive', hwc_id='0', sdm_config='0',
           same_surface_at_boundaries='True')


def read_csv(path, required):
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        if len(set(fields)) != len(fields) or not set(required) <= set(fields):
            raise ValueError(f'{path.name}: missing or duplicate columns')
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f'{path.name}:{reader.line_num}: malformed row')
            yield row


def check_window(w, state, ns):
    phase = w['phase']
    dc = str(int(state == 'on'))
    expected = dict(HDR, dc_label=state, panel_dc_pre=dc, panel_dc_post=dc,
                    pref_pre=dc, pref_post=dc)
    for key, value in expected.items():
        if w[key] != value:
            raise ValueError(f'{phase}: {key}={w[key]!r}, expected {value!r}')
    if not (float(w['sf_refresh_hz']) == float(w['sdm_fps']) == 120
            and int(w['exposure_ns']) == ns and int(w['sysfs_bl']) > 0):
        raise ValueError(f'{phase}: invalid refresh, exposure or BL')


def summarize(frames, w):
    phase, n = w['phase'], int(w['frames'])
    if n < 1 or sorted(int(f['frame_n']) for f in frames) != list(range(1, n+1)):
        raise ValueError(f'{phase}: missing, repeated or unbound frame')
    if any(not abs(float(f['exposure_us'])*1000 - int(w['exposure_ns'])) <= 1 for f in frames):
        raise ValueError(f'{phase}: frame exposure disagrees with window')
    ok = [f for f in frames if f['event_status'] == 'ok']
    summary = {}
    for key in METRICS:
        values = [float(f[key]) for f in (frames if key == 'mean_dn' else ok)]
        if not all(map(isfinite, values)):
            raise ValueError(f'{phase}: nonfinite {key}')
        summary[key] = (min(values), median(values), max(values)) if values else (None, None, None)
    return len(ok), n, summary


def depth_decision(counts, off, on, ret):
    if min(counts) < 3:
        return 'unresolved_insufficient_qualified'
    if abs(off[1] - ret[1]) > 3:
        return 'unresolved_off_drift'
    if min(off[1], ret[1]) - on[1] >= 3 and on[2] < min(off[0], ret[0]):
        return 'shallower_on'
    if on[1] - max(off[1], ret[1]) >= 3 and on[0] > max(off[2], ret[2]):
        return 'deeper_on'
    return 'unresolved'


def compare(frames_csv, windows_csv):
    frames, windows = defaultdict(list), {}
    for row in read_csv(frames_csv, ('phase', 'frame_n', 'exposure_us', 'event_status', *METRICS)):
        frames[row['phase']].append(row)
    for row in read_csv(windows_csv, (*HDR, 'phase', 'frames', 'sysfs_bl', 'dc_label', 'panel_dc_pre',
                                      'panel_dc_post', 'pref_pre', 'pref_post', 'sf_refresh_hz',
                                      'sdm_fps', 'exposure_ns', 'wake_epoch')):
        if row['phase'] in windows:
            raise ValueError(f"{row['phase']}: duplicate window")
        windows[row['phase']] = row

    for level, suffix, shutters in [('high', '', ('125', '200', '312')), ('low', 'Low', ('200', '312', '500'))]:
        conditions = set()
        for shutter in shutters:
            ns = EXPOSURE_NS[shutter]
            phases = [f'day_{state}{suffix}_{shutter}' for state in STATES]
            if suffix and not any(p in frames or p in windows for p in phases):
                continue
            if [p for p in windows if p in phases] != phases:
                raise ValueError(f'{level}/{shutter}: missing or out-of-order OFF/ON/return windows')
            stats = []
            for state, p in zip(STATES, phases):
                if p not in windows or p not in frames:
                    raise ValueError(f'{p}: missing frames or verified window')
                w = windows[p]
                check_window(w, state, ns)
                conditions.add((int(w['sysfs_bl']), int(w['wake_epoch'])))
                stats.append(summarize(frames[p], w))
            if len(conditions) != 1:
                raise ValueError(f'{level}/{shutter}: BL or wake epoch changed')

            role = {'312': 'primary', '200': 'support'}.get(shutter, 'secondary') if not suffix else 'exploratory'
            for metric in METRICS:
                row = dict(level=level, exposure_us=ns/1000, role=role, sysfs_bl=w['sysfs_bl'],
                           hz=w['sf_refresh_hz'], metric=metric)
                ranges = []
                for state, (qualified, total, summary) in zip(STATES, stats):
                    row[state+'_qualified'], row[state+'_total'] = qualified, total
                    values = summary[metric]
                    ranges.append(values)
                    for name, value in zip(('min', 'median', 'max'), values):
                        row[state+'_'+name] = value
                a, b, c = (v[1] for v in ranges)
                row['on_minus_avg_off_medians'] = b-(a+c)/2 if None not in (a, b, c) else None
                row['depth_decision'] = (depth_decision([s[0] for s in stats], *ranges)
                                         if metric == 'depth_pct' else None)
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
