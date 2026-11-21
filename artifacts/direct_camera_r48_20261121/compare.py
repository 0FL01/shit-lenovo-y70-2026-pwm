#!/usr/bin/env python3
"""R48: python3 -B compare.py frames.csv windows.csv field.csv > compare.csv

Default: field.csv is the four-level CAL/312.5 report. For a confirmed clipped
primary, retain its frames, windows and field312.csv; supply the independently
acquired all-level CAL/200 report as the positional field CSV:
  python3 -B compare.py frames.csv windows.csv field200.csv --clipped-primary-field field312.csv
Generate each field CSV separately with field.py FRAMES --us 312.5 or --us 200.
field.py exits nonzero on a clipped primary; its full report is still required.

One row per DAY shutter and metric. Use R44's qualified G1 event per release;
RAW-plane independence and receipt order come from the R48 window binder.
Pair visits, not frame indices: an edge is the difference of phase medians.
Subtract the lower DBV from the higher on *both* traversals. At a repeated
DBV subtract the earlier visit from the later. Never pool shutters or visits.

Each forward A/B/C/D and downward Dr/Cr/Br/Ar ramp has its own guard; LOW
(6692) intervenes. Compare separately acquired ramps at the same shutter;
same-DBV cross-guard differences measure scatter, not hysteresis. The separate
125-us sham is Q minus Bs. Never use Q as an endpoint of a physical DBV step.

CAL means use all four releases per DBV at one common shutter. Require all levels to
pass the common field check and their largest pairwise mean ratio to be <=1.05.
Depth calls also need >=3 independent qualified releases per relevant phase,
>=3 pp in the same direction on both ramps, and both empirical difference
ranges beyond the control/revisit scatter envelope. FWHM uses the same count
and separation rules in RAW rows, with no pp threshold. Numeric differences
are descriptive even when counts or CALs do not support a decision.
"""

import argparse
from collections import defaultdict
import csv
from math import isclose
from pathlib import Path
from statistics import fmean
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import compare as r44


UP = ('offA', 'offB', 'offC', 'offD')
DOWN = ('offDr', 'offCr', 'offBr', 'offAr')
SHAM = ('offBs', 'offQ')
DBV = dict(zip(UP, range(14055, 14059)))
DBV.update({s+'r': DBV[s] for s in UP}, offBs=14056, offQ=14056)
TOKENS = ('125', '200', '312')
EDGES = ('14055_14056', '14056_14057', '14057_14058')
METRICS = ('depth_pct', 'fwhm_raw_rows')
SDR = dict(scene='sdr', hwc_dynamic_range='SDR', sdm_dynamic_range='SDR', hdr_mode='NO_HDR',
           hbm_mode='off', hwc_id='0', sdm_config='0', panel_dc_pre='0', panel_dc_post='0',
           pref_pre='0', pref_post='0')


def bind(frames_csv, windows_csv):
    windows, slots, frames = [], defaultdict(dict), defaultdict(list)
    fields = (*SDR, 'phase', 'group', 'sysfs_bl', 'exposure_ns', 'frames', 'wake_epoch',
              'sf_refresh_hz', 'sdm_fps', 'guard_group')
    seen = set()
    for w in r44.read_csv(windows_csv, fields):
        p = w['phase']
        group, leg, token = p.split('_')
        if (p in seen or group != w['group'] or group not in ('day', 'cal') or leg not in DBV
                or int(w['sysfs_bl']) != DBV[leg] or any(w[k] != v for k, v in SDR.items())
                or not float(w['sf_refresh_hz']) == float(w['sdm_fps']) == 120):
            raise ValueError(f'{p}: duplicate or inconsistent SDR/120/stock OFF DBV window')
        seen.add(p)
        if token not in TOKENS or int(w['exposure_ns']) != r44.EXPOSURE_NS[token] or int(w['frames']) != 4:
            raise ValueError(f'{p}: expected four releases at the labeled R48 shutter')
        if group == 'day':
            slots[token][leg] = len(windows)
        elif leg not in UP:
            raise ValueError(f'{p}: unexpected level CAL')
        windows.append(w)
    if set(slots) != set(TOKENS) or len({int(w['wake_epoch']) for w in windows}) != 1:
        raise ValueError('expected three DAY shutters in a single bound wake epoch')
    if not {f'cal_{leg}_312' for leg in UP} <= seen:
        raise ValueError('missing common CAL/312 level')
    guards = [w['guard_group'].strip() for w in windows]
    if not all(guards):
        raise ValueError('missing guard_group in bound windows')
    for token, legs in slots.items():
        ramps = (UP, DOWN, SHAM) if token == '125' else (UP, DOWN)
        if set(legs) != {leg for ramp in ramps for leg in ramp} or legs[UP[-1]] >= legs[DOWN[0]]:
            raise ValueError(f'{token}: missing or misordered DAY ramps')
        for ramp in ramps:
            indices = [legs[leg] for leg in ramp]
            guard = guards[indices[0]]
            block = [i for i, g in enumerate(guards) if g == guard]
            if indices != block or indices != list(range(indices[0], indices[-1]+1)):
                raise ValueError(f'{token}/{ramp[0]}: expected one separate contiguous guard for {ramp}')
    for f in r44.read_csv(frames_csv, ('phase', 'frame_n', 'group', 'scene', 'exposure_us',
                                      'gate', 'event_status', *r44.METRICS)):
        p = f['phase']
        if (p not in seen or p.split('_')[:2] != [f['group'], f['scene']]
                or not f['event_status'] or (f['event_status'] == 'ok' and f['gate'] != 'ok')):
            raise ValueError(f'{p}/{f["frame_n"]}: unbound frame or inconsistent event')
        frames[p].append(f)
    stats = [r44.summarize(frames[w['phase']], w) for w in windows]
    cal_frames = {w['phase']: sorted(frames[w['phase']], key=lambda f: int(f['frame_n']))
                  for w in windows if w['group'] == 'cal'}
    return windows, slots, guards, stats, cal_frames


def field_status(path, windows, cal_frames, token, *, verify_clipping=False):
    """Bind exactly one common A/B/C/D CAL ramp to its guarded field report."""
    phases = [f'cal_{s}_{token}' for s in UP]
    cals = {w['phase']: w for w in windows if w['phase'] in phases}
    if list(cals) != phases:
        raise ValueError(f'expected complete ordered CAL/{token} windows at all four measured DBVs')
    group = cals[phases[0]]['guard_group']
    indices = [i for i, w in enumerate(windows) if w['guard_group'] == group]
    if ([windows[i]['phase'] for i in indices] != phases or indices[-1]-indices[0] != 3):
        raise ValueError(f'CAL/{token}: expected one independent contiguous guarded excursion')
    quarters, declared = defaultdict(dict), {}
    mean_cols = [f'g1_mean_dn{i}' for i in range(1, 5)]
    clip_cols = [f'clip{i}' for i in range(1, 5)]
    floor_cols = [f'floor{i}' for i in range(1, 5)]
    fields = ('phase', 'expected_dbv', 'scene', 'exposure_us', 'quarter', 'status', 'state_status',
              'n_required', 'n_present', 'g1_mean_dn', *mean_cols)
    if verify_clipping:
        fields += (*clip_cols, *floor_cols)
    for r in r44.read_csv(path, fields):
        p = r['phase']
        q = r['quarter']
        if (p not in cals or p != f"cal_{r['scene']}_{token}" or int(r['expected_dbv']) != int(cals[p]['sysfs_bl'])
                or float(r['exposure_us'])*1000 != int(cals[p]['exposure_ns'])
                or q in quarters[p] or q not in ('', '1', '2', '3', '4')
                or int(r['n_required']) != 4 or not r['status'] or not r['state_status']):
            raise ValueError(f'{p}: unbound or duplicate field result')
        if declared.setdefault(p, r['state_status']) != r['state_status']:
            raise ValueError(f'{p}: conflicting state_status in field.csv')
        if verify_clipping:
            # field.py counts any-CFA rails in a guard larger than R44's G1
            # ROI. A clipped guard need not clip G1, but a clipped G1 must be
            # visible in the guard of the same release. A floor is never cured.
            if r['state_status'] not in ('PASS', 'CLIPPED') or r['status'] != r['state_status']:
                raise ValueError(f'{p}: primary has a non-clipping failure; fallback blocked')
            clips = [int(r[c]) for c in clip_cols]
            clipped = any(clips)
            if (min(clips) < 0 or any(int(r[c]) != 0 for c in floor_cols)
                    or clipped != (r['status'] == 'CLIPPED') or clipped != (q == '')
                    or any(float(f['mean_dn']) < 20 or f['gate'] not in ('ok', 'clipped')
                           or (f['gate'] == 'clipped' and n == 0) for f, n in zip(cal_frames[p], clips))):
                raise ValueError(f'{p}: primary CAL rail counts, field status and frame gates disagree')
        if verify_clipping or r['state_status'] == 'PASS' or r['g1_mean_dn']:
            dns = [float(f['mean_dn']) for f in cal_frames[p]]
            if int(r['n_present']) != 4 or any(not isclose(float(r[col]), val, abs_tol=1e-6, rel_tol=1e-8)
                    for col, val in zip([*mean_cols, 'g1_mean_dn'], [*dns, fmean(dns)])):
                raise ValueError(f'{p}: field brightness does not match all four bound CAL releases')
        quarters[p][q] = r['status']
    by_bl = {}
    for p, w in cals.items():
        q = quarters[p]
        if declared.get(p) == 'PASS' and set(q.values()) != {'PASS'}:
            raise ValueError(f'{p}: field quarter and overall state disagree')
        status = declared.get(p, 'MISSING_CAL_FIELD')
        if status == 'PASS' and set(q) != set('1234'):
            status = 'MISSING_FIELD_QUARTERS'
        by_bl[int(w['sysfs_bl'])] = status
    return by_bl


def compare(frames_csv, windows_csv, field_csv, clipped_primary_field=None):
    windows, slots, guards, stats, cal_frames = bind(frames_csv, windows_csv)
    cal_token = '312'
    if clipped_primary_field is not None:
        primary = field_status(clipped_primary_field, windows, cal_frames, '312', verify_clipping=True)
        if set(primary.values()) - {'PASS', 'CLIPPED'} or 'CLIPPED' not in primary.values():
            raise ValueError('fallback requires a complete primary field report with clipping as its only failure')
        cal_token = '200'
    by_bl = field_status(field_csv, windows, cal_frames, cal_token)
    if cal_token == '200':
        order = list(cal_frames)
        if order.index('cal_offD_312') >= order.index('cal_offA_200'):
            raise ValueError('replacement CAL/200 must be acquired after the retained CAL/312')
        if set(by_bl.values()) != {'PASS'}:
            raise ValueError('fallback requires a passing CAL/200 field at all four levels')
    selected = {DBV[s]: cal_frames[f'cal_{s}_{cal_token}'] for s in UP}
    means = {dbv: fmean(float(f['mean_dn']) for f in series) for dbv, series in selected.items()}
    signal_ok = all(f['gate'] == 'ok' and float(f['mean_dn']) >= 20 for series in selected.values() for f in series)
    spread = (100*(max(means.values()) / min(means.values()) - 1) if min(means.values()) > 0 else None)
    cal_status = ('unresolved_field' if set(by_bl.values()) != {'PASS'} else
                  'unresolved_cal_signal' if not signal_ok or spread is None else
                  'confounded_cal_brightness' if spread > 5 + 1e-12 else 'matched')
    for token, legs in sorted(slots.items(), key=lambda t: r44.EXPOSURE_NS[t[0]]):
        for metric in METRICS:
            row = dict(exposure_us=r44.EXPOSURE_NS[token]/1000, metric=metric, cal_exposure_us=r44.EXPOSURE_NS[cal_token]/1000,
                       cal_max_vs_min_pct=spread, cal_status=cal_status)
            for dbv in sorted(means):
                row[f'cal_{dbv}_mean_dn'] = means[dbv]
                row[f'cal_{dbv}_field'] = by_bl[dbv]
            counts, values = {}, {}
            for leg in UP + DOWN + SHAM:
                i = legs.get(leg)
                n, total, v = (0, 0, (None,)*3) if i is None else (
                    stats[i][0], stats[i][1], stats[i][2][metric])
                row.update({leg+'_'+k: x for k, x in zip(
                    ('dbv', 'guard', 'qualified', 'total', 'min', 'median', 'max'),
                    (None if i is None else int(windows[i]['sysfs_bl']), guards[i] if i is not None else None,
                     n, total, *v))})
                counts[leg], values[leg] = n, v

            def contrast(low, high):
                """Return high-low empirical (smallest, median difference, largest)."""
                if not (counts[low] and counts[high]):
                    return None
                a, b = values[low], values[high]
                return b[0]-a[2], b[1]-a[1], b[2]-a[0]

            paired = {}
            for k, edge in enumerate(EDGES):
                lo, hi = UP[k:k+2]
                rlo, rhi = lo+'r', hi+'r'
                paired[edge] = (contrast(lo, hi), contrast(rlo, rhi))
                for direction, a, b, delta in zip(('forward', 'return'), (lo, rlo), (hi, rhi), paired[edge]):
                    row[f'{edge}_{direction}_high_minus_low'] = b+'-'+a
                    row[f'{edge}_{direction}_delta_median'] = delta[1] if delta else None

            sham = contrast(*SHAM)
            row['sham_Q_minus_Bs'] = sham[1] if sham else None
            revisits = {s: contrast(s, s+'r') for s in UP}
            for s, delta in revisits.items():
                row[s+'r_minus_'+s+'_revisit'] = delta[1] if delta else None

            # The null envelope is the largest absolute empirical difference
            # between any qualified releases of the control, sham or same-DBV
            # returns. These bounds are descriptive, not confidence intervals.
            for k, edge in enumerate(EDGES[:2]):
                forward, ret = paired[edge]
                levels = sorted(set(UP[k:k+2] + UP[-2:]))
                required = levels + [s+'r' for s in levels] + (list(SHAM) if token == '125' else [])
                nulls = [*paired[EDGES[-1]], *(revisits[s] for s in levels)] + ([sham] if token == '125' else [])
                bound = (max(max(abs(x[0]), abs(x[2])) for x in nulls) if all(nulls) else None)
                row[edge+'_control_revisit_max_abs'] = bound
                if cal_status != 'matched':
                    decision = cal_status
                elif min(counts[s] for s in required) < 3:
                    decision = 'unresolved_insufficient_qualified'
                elif metric == 'fwhm_raw_rows':
                    if min(forward[0], ret[0]) > bound:
                        decision = 'wider_at_higher_dbv'
                    elif max(forward[2], ret[2]) < -bound:
                        decision = 'narrower_at_higher_dbv'
                    else:
                        decision = 'width_not_distinct_on_both_ramps'
                elif min(forward[1], ret[1]) >= 3 and min(forward[0], ret[0]) > bound:
                    decision = 'deeper_at_higher_dbv'
                elif max(forward[1], ret[1]) <= -3 and max(forward[2], ret[2]) < -bound:
                    decision = 'shallower_at_higher_dbv'
                else:
                    decision = 'no_distinct_3pp_step_on_both_ramps_resolved'
                row[edge+'_depth_decision'] = decision if metric == 'depth_pct' else None
                row[edge+'_width_pattern'] = decision if metric == 'fwhm_raw_rows' else None
            yield row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('frames', 'windows', 'field'):
        ap.add_argument(name, type=Path, metavar=name+'.csv')
    ap.add_argument('--clipped-primary-field', type=Path, metavar='field312.csv',
                    help='require original CAL/312 clipping evidence and use the positional all-level CAL/200 field report')
    args = ap.parse_args()
    try:
        rows = list(compare(args.frames, args.windows, args.field, args.clipped_primary_field))
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
