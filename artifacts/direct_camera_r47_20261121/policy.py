#!/usr/bin/env python3
"""Bind one stock HDR brightness excursion: python3 -B policy.py ARCHIVE > policy.csv

Each POINT tag req=FLOAT bl=INT names its own R46-style snapshots. Requests are
manual SDR settings; the Photonic Modulator reports normalized framework values,
SF nits are estimates, and sysfs BL is a separate integer observation. Neither
the BL threshold nor a PQ output identifies a native APL send or the Dolby gate.

The first request is the reference. Bind each different request to the next
return to that reference, in receipt order. A candidate is a requested step,
not necessarily above threshold. sysfs_threshold_step compares consecutive BL
samples only; the exact intervening trajectory is unknown. Exit 3 with CSV for an incomplete
excursion or a return that differs in applied brightness. Invalid snapshots or
mixed surfaces/epochs exit 2 without CSV. Use separate archives for other clips.
"""

import argparse
import csv
from math import isclose, isfinite
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121 import state, windows as r43
from direct_camera_r44_20261121.windows import snapshot
from direct_camera_r46_20261121.windows import video_sample


POINT = re.compile(r'POINT ([A-Za-z0-9][A-Za-z0-9_-]*) req=((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?) bl=(\d+)')
THRESHOLD = 16000  # selected DT: strictly greater, not greater-or-equal


def receipts(archive):
    seen = set()
    for i, line in enumerate(r43.original(archive / 'acquisition.log').read_text().splitlines(), 1):
        if line.split(maxsplit=1)[:1] != ['POINT']:
            continue
        m = POINT.fullmatch(line)
        r43.require(m and m[1] not in seen and 0 <= float(m[2]) <= 1,
                    f'acquisition.log:{i}: invalid or repeated POINT')
        seen.add(m[1])
        yield m[1], float(m[2]), int(m[3])
    r43.require(seen, 'acquisition.log: no POINT receipts')


def display_policy(sf, display):
    """Select the built-in output/controller; exclude capability tables and brightness history."""
    ident = state.value(sf, r'^Display (\d+) \(HWC display 0\):')
    comp = state.physical(sf, ident)
    sdm = state.block(sf, r'^SDM3 display_id: 0[ \t]*\n', r'^(?:SDM3 display_id:|OverlayProperties:)')
    controllers = re.split(r'^Display Power Controller:[ \t]*$', display, flags=re.M)[1:]
    mains = [c for c in controllers if re.search(r'^  mDisplayId=0$',
             c.partition('Display Power Controller Locked State:')[0], re.M)]
    r43.require(len(mains) == 1, 'expected one built-in Display Power Controller')
    main, = mains
    settings = state.section(main, 'DisplayBrightnessController')
    mod = state.section(main, 'Photonic Modulator State')
    hdr = state.section(main, 'HdrBrightnessModifier')
    hbm = state.section(main, 'HighBrightnessModeController')
    thermal = state.section(main, 'BrightnessThermalClamper')

    out = dict(
        sdr_setting=state.field(settings, 'mCurrentScreenBrightness'),
        fw_actual_sdr_backlight=state.field(mod, 'mActualSdrBacklight'),
        fw_actual_hdr_backlight=state.field(mod, 'mActualBacklight'),
        sf_sdr_white_nits=state.value(comp, rf'^ +displayBrightnessNits=\S+ sdrWhitePointNits=({state.NUM})\b', float),
        sf_display_nits=state.value(comp, rf'^ +displayBrightnessNits=({state.NUM})\b', float),
        hdr_max_desired_ratio=state.field(hdr, 'mMaxDesiredHdrRatio'),
        hdr_modifier_max=state.field(hdr, 'mMaxBrightness'),
        hbm_stats_state=state.field(hbm, 'mHbmStatsState', r'HBM_\w+', str),
        hdr_boost_applied=state.field(hbm, 'mHdrBoostBrightnessApplied'),
        hdr_boost_disabled=state.boolean(hbm, 'mHdrBoostDisabled'),
        cached_min=state.field(main, 'mCachedBrightnessInfo.brightnessMin'),
        cached_max=state.field(main, 'mCachedBrightnessInfo.brightnessMax'),
        cached_max_reason=state.field(main, 'mCachedBrightnessInfo.brightnessMaxReason', r'\d+', int),
        hbm_current_min=state.field(hbm, 'mCurrentMin'), hbm_current_max=state.field(hbm, 'mCurrentMax'),
        hbm_min=state.field(hbm, 'mBrightnessMin'), hbm_max=state.field(hbm, 'mBrightnessMax'),
        hbm_max_raw=state.field(hbm, 'mBrightnessMaxRaw'), hbm_max_cap=state.field(hbm, 'mBrightnessMaxCap'),
        sdm_max_bl=state.value(sdm, r'^ FPS [^\n]*?\bMaxBrightness:(\d+)[ \t]*$', int),
        brightness_reason=state.field(main, 'mBrightnessReason', r'manual(?: \[ [\w +]+ \])?', str),
        throttling_reason=state.field(hbm, 'mThrottlingReason', r'\w+', str),
        thermal_cap=state.field(thermal, 'mBrightnessCap'), thermal_cap_applied=state.boolean(thermal, 'mApplied'),
        dolby_hwc_supported=state.value(comp, r'^ +HWC Support:[^\n]*?\bdv=(true|false)\b'),
    )
    for key, val in out.items():
        r43.require(val is not None and (not isinstance(val, float) or isfinite(val)),
                    f'missing, ambiguous or invalid {key}')
    r43.require(state.boolean(hbm, 'mIsAutoBrightnessEnabled') is False and
                state.boolean(main, 'mScreenBrightnessRampAnimator.isAnimating()') is False and
                state.boolean(mod, 'mBacklightChangeInProgress') is False and
                state.field(mod, 'mActualState', r'\w+', str) == 'ON', 'manual brightness not settled')
    r43.require(out['throttling_reason'] == 'none' and not out['thermal_cap_applied'], 'brightness throttled')
    return out


def close(a, b):
    # Framework floats are printed with fewer digits than the command arguments.
    return isclose(a, b, rel_tol=0, abs_tol=1e-7)


def bind_returns(rows):
    ref = rows[0]
    ref_req = ref['req_sdr']
    candidates = []
    complete = False
    for i, row in enumerate(rows):
        row.update(role='reference', reference_tag=ref['tag'], candidate_tags='', return_tag='',
                   delta_bl_from_reference=row['sysfs_bl'] - ref['sysfs_bl'], return_status='')
        if not close(row['req_sdr'], ref_req):
            row.update(role='candidate', candidate_tags=row['tag'], return_status='missing_return')
            candidates.append(row)
        elif i:
            restored = (row['sysfs_bl'] == ref['sysfs_bl'] and all(close(row[k], ref[k]) for k in
                        ('sdr_setting', 'fw_actual_sdr_backlight', 'fw_actual_hdr_backlight', 'hdr_sdr_ratio')))
            status = 'matched' if restored else 'applied_brightness_differs'
            if candidates:
                row.update(role='return', candidate_tags=' '.join(c['tag'] for c in candidates),
                           return_tag=row['tag'], return_status=status)
                for c in candidates:
                    c.update(return_tag=row['tag'], return_status=status)
                candidates = []
                complete = True
            else:
                row.update(role='same_request_control', return_status=status)
            ref = row
    return complete and all(r['return_status'] in ('', 'matched') for r in rows)


def bind(archive):
    rows = []
    previous = None
    epoch_path = archive / 'epoch'
    epoch = int(r43.original(epoch_path).read_text()) if epoch_path.exists() else None
    for tag, req, bl in receipts(archive):
        def read(suffix):
            return r43.original(archive / f'{tag}.{suffix}').read_text()

        try:
            if epoch is None:
                epoch = int(read('wake'))
            r43.require(epoch > 0, 'invalid wake epoch')
            snap, seq = snapshot(archive, tag, scene='hdr', bl=bl, hwc=0, hz=120, wake=epoch, intent='off')
            r43.require((snap['hdr_mode'], snap['hbm_mode']) == ('HBM_HDR', 'hdr'), 'expected current HDR HBM')
            sf = read('sf')
            name, frame = video_sample(sf)
            r43.require(name.rsplit('#', 1)[1] == str(seq), 'physical video identity mismatch')
            r43.require(previous is None or (previous[0] == name and frame > previous[1]),
                        'surface changed or its frame counter did not advance')
            policy = display_policy(sf, read('display'))
            r43.require(0 < bl <= policy['sdm_max_bl'], 'sysfs BL outside reported SDM range')
        except (ValueError, OSError) as exc:
            raise ValueError(f'{tag}: {exc}') from None
        prev = rows[-1] if rows else None
        step = '' if prev is None else 'none'
        if prev and (bl > THRESHOLD) != prev['sysfs_bl_above_16000']:
            step = 'up' if bl > THRESHOLD else 'down'
        rows.append(dict(tag=tag, req_sdr=req, request_matches_setting=close(req, policy['sdr_setting']),
                         **snap, **policy,
                         frame_delta='' if previous is None else frame - previous[1],
                         previous_tag=prev['tag'] if prev else '', previous_bl=prev['sysfs_bl'] if prev else '',
                         sysfs_bl_above_16000=bl > THRESHOLD, sysfs_threshold_step=step, dolby_range_reported=False,
                         driver_dolby_gate='unknown', native_apl_send='not_evaluated'))
        previous = name, frame
    lo, hi = min(r['sysfs_bl'] for r in rows), max(r['sysfs_bl'] for r in rows)
    for row in rows:
        row.update(observed_min_bl=lo, observed_max_bl=hi)
    return rows, bind_returns(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    args = ap.parse_args()
    try:
        rows, closed = bind(args.archive)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)
    if not closed:
        ap.exit(3, 'no complete brightness excursion with a matching return for every candidate\n')


if __name__ == '__main__':
    main()
