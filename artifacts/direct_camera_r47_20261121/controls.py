#!/usr/bin/env python3
"""Bind the separate R47 control archive: python3 -B controls.py ARCHIVE frames.csv > control_windows.csv

One row per closed optical window in receipt order. R44 binds originals, both
stock snapshots and the single HDR video surface; R46 checks its frame counter.
The TX receipt immediately preceding each PRE identifies the numerical request
and native tag. The lower sham must repeat lower_B's request, not just its BL.
Every row carries its measured BL's independent 500-us CAL pair: guarded R43
field_status and the two-release mean G1 DN above tagged black in the fixed ROI.
Failed field checks remain diagnostic rows, including their measured brightness.

Consume the external dispatch.py ARCHIVE > dispatch.csv table via stdout; if
ARCHIVE/dispatch.csv is present, require it to reproduce. Only the dispatch
table's exact LP packet sets and APL-caller returns establish dispatch; the DC reads
describe Flicker prevention. Neither is a DDIC readback. Each excursion starts
below threshold, so upper_A and reverse_A are upward entries as well.
"""

import argparse
import csv
from decimal import Decimal
from io import StringIO
from pathlib import Path
import re
from statistics import fmean
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.measure import read_sites
from direct_camera_r43_20261121.geometry import qualify
from direct_camera_r43_20261121.windows import original, require
from direct_camera_r44_20261121.windows import bind as bind_originals
from direct_camera_r46_20261121.windows import add_frame_deltas
from direct_camera_r47_20261121.windows import add_boundary_times


# Acquisition order, not alphabetical. 'none' means no measured APL send in
# the tagged request, not APL OFF. The upper same-side steps start above 16000.
SCHEDULE = (
    ('cal_offN_500', 'cals_N', 15999, 'none'),
    ('cal_offZ_500', 'cals_Z', 16000, 'none'),
    ('cal_offP_500', 'cals_P', 16001, 'on'),
    ('cal_offQ_500', 'cals_Q', 16002, 'none'),
    ('day_offLA_312', 'lower_A', 15999, 'none'),
    ('day_offLB_312', 'lower_B', 16000, 'none'),
    ('day_offSham_312', 'lower_Sham', 16000, 'none'),
    ('day_offLC_312', 'lower_C', 15999, 'none'),
    ('day_offUA_312', 'upper_A', 16002, 'on'),
    ('day_offUB_312', 'upper_B', 16001, 'none'),
    ('day_offUC_312', 'upper_C', 16002, 'none'),
    ('day_offRA_312', 'reverse_A', 16001, 'on'),
    ('day_offRB_312', 'reverse_B', 16000, 'off'),
    ('day_offRC_312', 'reverse_C', 16001, 'on'),
)


def preceding_requests(log):
    requests, tags = {}, set()
    pending = active = None
    for line in original(log).read_text().splitlines():
        kind = line.split(maxsplit=1)[:1]
        if kind == ['TX']:
            m = re.fullmatch(r'TX (\w+) request=(0\.\d+|1\.0|none) settled=(\d+)', line)
            require(m and not active and m[1] not in tags, f'invalid, repeated or mid-window TX: {line}')
            tags.add(m[1])
            pending = (m[1], m[2], int(m[3]))
        elif kind == ['PRE']:
            active = line.split()[1]  # R44 has already validated the PRE/POST grammar and inventory
            require(pending is not None, f'{active}: missing preceding TX')
            requests[active], pending = pending, None
        elif kind == ['POST']:
            active = None
    return requests


def dispatch_table(archive):
    # Decode this archive's originals rather than accepting a same-named tag
    # from another run. The independent dispatch CSV is reproducible verbatim.
    proc = subprocess.run([sys.executable, '-B', Path(__file__).with_name('dispatch.py'), archive],
                          capture_output=True, text=True)
    require(proc.returncode == 0, f'dispatch.py failed: {proc.stderr.strip()}')
    saved = archive / 'dispatch.csv'
    if saved.exists() or saved.is_symlink():
        require(original(saved).read_text() == proc.stdout, 'dispatch.csv differs from this archive’s native traces')
    return {r['tag']: r for r in csv.DictReader(StringIO(proc.stdout), strict=True)}


def check_dispatch(d, expected):
    tag = d['tag']
    require(d['bracket'] == d['trace_status'] == 'ok' and d['loss_notices'] == d['invalid_tx'] == '0',
            f'{tag}: incomplete native packet or probe trace')
    require(all(d[k] == '0' for k in ('exact_hbm_on', 'exact_hbm_off', 'hs_prefix_only_on', 'hs_prefix_only_off')),
            f'{tag}: confounding HBM set or HS prefix')
    require((d['exact_apl_on'], d['exact_apl_off']) ==
            (str(int(expected == 'on')), str(int(expected == 'off'))), f'{tag}: expected APL dispatch {expected}')
    count = int(expected != 'none')
    require(d['apl_entries'] != '' and (d['apl_send_returns'], d['apl_send_rc_hist']) ==
            (str(count), '0:1' if count else '') and int(d['apl_entries']) >= count,
            f'{tag}: APL probes or caller return inconsistent with {expected}')


def add_calibrations(frames, rows):
    seen, by_bl = set(), {}
    for row in rows:
        if row['group'] != 'cal':
            continue
        phase, bl = row['phase'], row['sysfs_bl']
        require(bl not in by_bl, f'{phase}: duplicate CAL pair for BL {bl}')
        pair = {i: frames / f'{phase}__{i}.dng' for i in (1, 2)}
        detail = ''
        try:
            field = qualify(phase.split('_')[1], 500, pair, seen)
        except ValueError as exc:
            # The original DNG closure passed; a failure of the additional
            # CAL-patch independence or field checks must remain visible.
            field, detail = [{'status': 'FAIL_CAL'}], str(exc)
        failed = {r['status'] for r in field if r['status'] != 'PASS'}
        means = []
        for path in pair.values():
            meta, sites = read_sites(path, 500)
            means.append(sites['G1'].mean() - meta['black_levels'][0])
        by_bl[bl] = dict(cal_phase=phase, cal_g1_mean_dn=format(fmean(means), '.9g'),
                         field_status=';'.join(sorted(failed)) if failed else 'PASS', field_detail=detail,
                         field_quarters_pass=sum(r['status'] == 'PASS' for r in field))
    for row in rows:
        row.update(by_bl[row['sysfs_bl']])


def bind(archive, frames_csv):
    rows = bind_originals(archive, frames_csv)
    require([r['phase'] for r in rows] == [p for p, *_ in SCHEDULE], 'incomplete or misordered R47 control phases')
    add_frame_deltas(archive, rows)
    add_boundary_times(archive, rows)
    requests = preceding_requests(archive / 'acquisition.log')
    traces = dispatch_table(archive)
    previous_post = 0
    for row, (phase, tag, bl, expected) in zip(rows, SCHEDULE):
        is_cal = phase.startswith('cal_')
        require((row['sysfs_bl'], row['exposure_ns'], row['frames']) ==
                (bl, 500000 if is_cal else 312500, 2 if is_cal else 4), f'{phase}: wrong drive, shutter or count')
        require((row['dc_label'], row['panel_dc_pre'], row['panel_dc_post'], row['pref_pre'], row['pref_post']) ==
                ('off', 0, 0, 0, 0), f'{phase}: expected stock Flicker prevention OFF at both boundaries')
        require((row['scene'], row['hdr_mode'], row['hbm_mode']) == ('hdr', 'HBM_HDR', 'hdr') and
                (row['hwc_id'], row['sf_refresh_hz'], row['sdm_config'], row['sdm_fps']) == (0, 120, 0, 120)
                and row['same_surface_at_boundaries'], f'{phase}: expected one stock HDR surface at HWC 0/120')
        tx_tag, request, settled = requests[phase]
        require(tx_tag == tag and request != 'none' and settled == bl, f'{phase}: wrong native request receipt')
        if tag == 'lower_Sham':
            require(Decimal(request) == Decimal(requests['day_offLB_312'][1]), f'{tag}: request differs from lower_B')

        capture = original(archive / f'{tag}.capture')
        klog = original(archive / f'{tag}.klog')
        settles = [s for s in capture.read_text(errors='replace').splitlines() if s.startswith('R47_SETTLE')]
        require(settles == [f'R47_SETTLE {bl}'] * 3, f'{tag}: missing or inconsistent native settling samples')
        require(tag in traces, f'{phase}: tag missing from dispatch.csv')
        d = traces[tag]
        check_dispatch(d, expected)
        begin, end = (Decimal(d[k])*1000 for k in ('begin_s', 'end_s'))
        require(previous_post <= begin <= end <= row['display_uptime_ms_pre'],
                f'{phase}: native request outside interval between prior POST and this PRE')
        previous_post = row['display_uptime_ms_post']
        row.update(native_tag=tag, native_capture=capture.name, native_klog=klog.name, request_sdr=request,
                   dispatch_begin_s=d['begin_s'], dispatch_end_s=d['end_s'], native_apl_send=expected,
                   exact_apl_on=d['exact_apl_on'], exact_apl_off=d['exact_apl_off'],
                   apl_send_returns=d['apl_send_returns'], apl_send_rc_hist=d['apl_send_rc_hist'])
    add_calibrations(archive / 'frames', rows)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', type=Path, metavar='ARCHIVE')
    ap.add_argument('frames_csv', type=Path, metavar='frames.csv')
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(f'R47 control windows blocked: {exc}')
    writer = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


if __name__ == '__main__':
    main()
