#!/usr/bin/env python3
"""R42 day: python3 -B pairs.py frames.csv windows.csv > pairs.csv

One row per exposure and G1 metric. Window order comes from windows.py, not
the sorted frame table. All per-window statistics use event_status=ok only.
For the point difference, the two repeated-window medians have equal weight.
For the range difference, use every qualified frame from both return windows:
[min(loaded)-max(core), max(loaded)-min(core)]. Only depth has a decision;
its gap must strictly exceed both white-control spans. This is a per-exposure
repeatability rule, not a statistical significance test or a panel claim.
"""

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
import sys


# R41 empirical full-white ranges, percentage points (R42 result.md).
PLAN = {
    'd312': (312500, Decimal('0.61'), ('core', 'loaded', 'coreRet')),
    'd200': (200000, Decimal('1.46'), ('core', 'loaded', 'coreRet')),
    'd500': (500000, Decimal('1.08'), ('loaded', 'core', 'loadedRet')),
}
METRICS = {'depth_pct': 'pp', 'michelson_pct': 'pp', 'fwhm_raw_rows': 'RAW_rows',
           'min_dn': 'DN', 'local_plateau_dn': 'DN', 'mean_dn': 'DN'}
ROLES = ('full', 'before', 'middle', 'repeat', 'full_return')
WINDOW_FIELDS = 'phase scene sysfs_bl hwc_both refresh_both exposure_ns iso frames profile wake_epoch group_both sf_rgb_both'
FRAME_FIELDS = 'phase scene group frame_n exposure_us iso y0 y1 x0 x1 gate event_status left_status right_status'


def require(test, message):
    if not test:
        raise ValueError(message)


def csv_rows(path, required):
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        require(len(set(fields)) == len(fields) and set(required) <= set(fields),
                f'{path.name}: missing or duplicate columns')
        for row in reader:
            require(None not in row and None not in row.values(), f'{path.name}:{reader.line_num}: malformed row')
            yield row


def number(row, key):
    try:
        value = Decimal(row[key])
    except InvalidOperation:
        raise ValueError(f'{row["phase"]}: invalid {key}') from None
    require(value.is_finite(), f'{row["phase"]}: nonfinite {key}')
    return value


def day_phase(phase):
    tokens = phase.split('_')
    groups = [t for t in tokens if t in PLAN]
    if not groups:
        return None
    require(len(tokens) == 2 and len(groups) == 1, f'{phase}: ambiguous day phase')
    group, = groups
    scene = tokens[1] if tokens[0] == group else tokens[0]
    require(scene in ('full', *PLAN[group][2], 'fullRet', 'dark', 'ring', 'inverse'),
            f'{phase}: unexpected scene for this exposure')
    return group, scene


def load(frame_path, window_path):
    windows, frames, order = {}, {}, {g: [] for g in PLAN}
    state = None
    for w in csv_rows(window_path, WINDOW_FIELDS.split()):
        ph = w['phase']
        key = day_phase(ph)
        if key is None:
            continue
        group, scene = key
        require(key not in windows and w['scene'] == scene.removesuffix('Ret'),
                f'{ph}: duplicate window or mismatched local scene')
        require(w['profile'] == 'active_0x8e' and w['sysfs_bl'] == '6692' and w['hwc_both'] == '0'
                and number(w, 'refresh_both') == 120 and w['iso'] == '6400'
                and int(w['exposure_ns']) == PLAN[group][0] and int(w['frames']) > 0,
                f'{ph}: unexpected day window settings or count')
        receipt = tuple(w[k] for k in ('wake_epoch', 'group_both', 'sf_rgb_both'))
        require(all(receipt) and state in (None, receipt), f'{ph}: missing or changed session/SF state')
        state = receipt
        windows[key], frames[key] = w, {}
        if scene not in ('dark', 'ring', 'inverse'):
            order[group].append(scene)

    for group, (_, _, triple) in PLAN.items():
        expected = ('full', *triple, 'fullRet')
        require(order[group] == [s for s in expected if (group, s) in windows],
                f'{group}: full / treatment / return windows out of acquisition order')

    for r in csv_rows(frame_path, [*FRAME_FIELDS.split(), *METRICS]):
        ph = r['phase']
        key = day_phase(ph)
        if key is None:
            require(r['group'] not in PLAN, f'{ph}: inconsistent day group')
            continue
        require(key == (r['group'], r['scene']) and key in windows and windows[key]['phase'] == ph,
                f'{ph}: frame has no matching day window/scene')
        n, w = int(r['frame_n']), windows[key]
        require(1 <= n <= int(w['frames']) and n not in frames[key], f'{ph}/{n}: unbound or duplicate frame')
        require(r['iso'] == w['iso'] and abs(number(r, 'exposure_us') * 1000 - int(w['exposure_ns'])) <= 1
                and tuple(r[k] for k in ('y0', 'y1', 'x0', 'x1')) == ('630', '1250', '754', '799'),
                f'{ph}/{n}: frame exposure, ISO or ROI mismatch')
        event = None
        require(r['event_status'], f'{ph}/{n}: missing event status')
        if r['event_status'] == 'ok':
            require(r['gate'] == r['left_status'] == r['right_status'] == 'ok'
                    and r['scene'] not in ('dark', 'ring', 'inverse'), f'{ph}/{n}: inconsistent G1 event')
            event = {k: number(r, k) for k in METRICS}
        frames[key][n] = event

    for key, w in windows.items():
        require(len(frames[key]) == int(w['frames']), f'{w["phase"]}: incomplete frame inventory')
    return windows, frames


def comparisons(windows, frames):
    for group, (ns, empirical, triple) in PLAN.items():
        scenes = ('full', *triple, 'fullRet')
        for metric, unit in METRICS.items():
            row = dict(group=group, exposure_us=Decimal(ns)/1000, metric=metric, difference_unit=unit)
            values = {}
            for role, scene in zip(ROLES, scenes):
                key = group, scene
                samples = frames.get(key, {})
                xs = values[scene] = [e[metric] for e in samples.values() if e is not None]
                row.update({role+'_phase': windows.get(key, {}).get('phase'), role+'_ok_n': len(xs),
                            role+'_total': len(samples), role+'_min': min(xs) if xs else None,
                            role+'_median': median(xs) if xs else None, role+'_max': max(xs) if xs else None})

            short = [s for s in scenes if len(values[s]) < 2]
            row.update(insufficient_windows=';'.join(short), loaded_minus_core=None,
                       range_diff_low=None, range_diff_high=None, depth_gap_pp=None,
                       fresh_full_span_pp=None, r41_span_pp=None, threshold_pp=None, depth_decision=None)
            depth = metric == 'depth_pct'
            if depth:
                row['r41_span_pp'] = empirical
                if min(len(values['full']), len(values['fullRet'])) >= 2:
                    white = values['full'] + values['fullRet']
                    row['fresh_full_span_pp'] = max(white) - min(white)
                    row['threshold_pp'] = max(empirical, row['fresh_full_span_pp'])
                row['depth_decision'] = 'insufficient'
            if not short:
                before, middle, repeat = triple
                repeated = (median(values[before]) + median(values[repeat])) / 2
                delta = median(values[middle]) - repeated
                pooled = values[before] + values[repeat]
                loaded, core = (values[middle], pooled) if middle == 'loaded' else (pooled, values[middle])
                lo, hi = min(loaded)-max(core), max(loaded)-min(core)
                row.update(loaded_minus_core=delta if middle == 'loaded' else -delta,
                           range_diff_low=lo, range_diff_high=hi)
                if depth:
                    threshold = row['threshold_pp']
                    row.update(depth_gap_pp=max(0, lo, -hi),
                               depth_decision=('loaded_deeper' if lo > threshold else 'loaded_shallower'
                                               if -hi > threshold else 'not_resolved'))
            yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path, metavar='frames.csv')
    ap.add_argument('windows', type=Path, metavar='windows.csv')
    args = ap.parse_args()
    try:
        rows = list(comparisons(*load(args.frames, args.windows)))
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(exc.strerror if isinstance(exc, OSError) else str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
