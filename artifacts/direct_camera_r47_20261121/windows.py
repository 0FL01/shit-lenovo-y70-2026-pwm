#!/usr/bin/env python3
"""Bind the R47 stock HDR brightness bracket: python3 -B windows.py ARCHIVE [frames.csv]

Each (group, shutter) needs offA (BL <=16000), offB (>16000), then offC
(same BL as offA). Capture either all slots by leg, or one consecutive A/B/C
triple per slot in any slot order. The entire archive must share a wake epoch
and playing surface, with one BL per leg. Use a separate archive for controls.
Flicker prevention stays OFF at both boundaries of every window.
Each leg needs cal_1250 and day_125/200/312 (312 means 312.5 us); cal_4000,
cal_500 and day_500 are independent optional windows. Shutters and release
counts must match across the three legs. Use R44 measure.py for frames.csv.

On success, stdout contains windows.csv. A probe-only archive exits 0 with a
diagnostic on stderr and empty stdout. Incomplete optical evidence exits 2.
BL identifies a side of the threshold, not an APL state: native APL dispatch
needs the external transition trace. No window has a native APL readback.
"""

import argparse
import csv
from itertools import groupby
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121 import windows as r43
from direct_camera_r44_20261121 import windows as r44
from direct_camera_r46_20261121 import windows as r46


THRESHOLD = 16000
LEGS = ('offA', 'offB', 'offC')
REQUIRED = {('cal', '1250'), ('day', '125'), ('day', '200'), ('day', '312')}
ALLOWED = REQUIRED | {('cal', '4000'), ('cal', '500'), ('day', '500')}


def has_optics(archive, frames_csv):
    """Do not mistake an orphaned frame, boundary or receipt for a clean pilot."""
    r43.require(archive.is_dir(), 'archive directory missing')
    log = archive / 'acquisition.log'
    if log.exists() or log.is_symlink():
        if re.search(r'^\s*(?:PRE|POST|frame)(?:\s|$)', r43.original(log).read_text(), re.M):
            return True
    frames = archive / 'frames'
    if frames.exists() or frames.is_symlink():
        if any(p.name.lower().endswith(('.dng', '.partial')) for p in frames.iterdir()):
            return True
    if any(re.match(r'(?:cal|day)_.*-(?:pre|post)\.', p.name) for p in archive.iterdir()):
        return True
    if frames_csv.exists() or frames_csv.is_symlink():
        # A zero-length redirected measurement or a valid header without rows
        # contains no frames. A malformed table remains an error.
        if r43.original(frames_csv).stat().st_size and r43.read_frames(frames_csv):
            return True
    return False


def check_bracket(rows):
    drives, inventories = {}, {leg: {} for leg in LEGS}
    sequence = []
    for row in rows:  # R44 returns acquisition order, not sorted file names
        phase = row['phase']
        match = re.fullmatch(r'(cal|day)_(off[ABC])_([0-9]+)', phase)
        r43.require(match, f'{phase}: unexpected R47 phase')
        group, leg, shutter = match.groups()
        slot = group, shutter
        r43.require(slot in ALLOWED, f'{phase}: unexpected shutter for {group}')
        inventory = inventories[leg]
        r43.require(slot not in inventory, f'{phase}: repeated window')
        inventory[slot] = row['frames']
        sequence.append((slot, leg))

        bl = row['sysfs_bl']  # R44 matches both actual sysfs samples to the receipt
        r43.require((bl > THRESHOLD) == (leg == 'offB'), f'{phase}: BL {bl} on wrong threshold side')
        r43.require(drives.setdefault(leg, bl) == bl, f'{phase}: BL changed within {leg}')
        r43.require((row['dc_label'], row['panel_dc_pre'], row['panel_dc_post'],
                     row['pref_pre'], row['pref_post']) == ('off', 0, 0, 0, 0),
                    f'{phase}: expected provider and panelDC OFF throughout the sampled boundaries')
        r43.require((row['hwc_id'], row['sf_refresh_hz'], row['sdm_config'], row['sdm_fps']) ==
                    (0, 120, 0, 120), f'{phase}: expected actual HWC/SDM 0 at 120 Hz')
        r43.require((row['scene'], row['hdr_mode'], row['hbm_mode']) == ('hdr', 'HBM_HDR', 'hdr'),
                    f'{phase}: expected actual stock HDR/HBM')
        r43.require(row['same_surface_at_boundaries'], f'{phase}: video SurfaceView changed')
        row.update(brightness_leg=leg, bl_minus_threshold=bl - THRESHOLD,
                   native_apl_evidence='requires_external_dispatch_trace')

    for leg, inventory in inventories.items():
        missing = REQUIRED - inventory.keys()
        r43.require(not missing, f'{leg}: missing required windows {sorted(missing)}')
        r43.require(inventory == inventories['offA'], f'{leg}: shutter or release inventory differs from offA')
    r43.require(drives['offC'] == drives['offA'], 'offC did not return to the offA BL')

    leg_runs = tuple(leg for leg, _ in groupby(leg for _, leg in sequence))
    if leg_runs != LEGS:
        # A slot-wise run must close each bracket before starting another slot.
        # Filtering by slot first would hide interleaved or mixed schedules.
        for (group, shutter), block in groupby(sequence, key=lambda item: item[0]):
            legs = tuple(leg for _, leg in block)
            r43.require(legs == LEGS, f'{group}_{shutter}: expected consecutive {LEGS}, observed {legs}')


def add_boundary_times(archive, rows):
    # dumpsys display prints a target uptime and its age at dump time. Their
    # sum dates the boundary independently of host file mtimes and video fps.
    pattern = r'^ +mLightSensorEnableTime=(\d+) \((\d+) ms ago\)[ \t]*$'
    previous = None
    for row in rows:
        phase = row['phase']
        for side in ('pre', 'post'):
            path = archive / f'{phase}-{side}.display'
            times = re.findall(pattern, r43.original(path).read_text(), re.M)
            r43.require(len(times) == 1, f'{path.name}: missing or ambiguous display dump uptime')
            stamp = sum(map(int, times[0]))
            r43.require(previous is None or (stamp > previous if side == 'post' else stamp >= previous),
                        f'{path.name}: nonchronological display dump uptime')
            row[f'display_uptime_ms_{side}'] = previous = stamp


def bind(archive, frames_csv):
    if not has_optics(archive, frames_csv):
        return []
    rows = r44.bind(archive, frames_csv)
    check_bracket(rows)
    r46.add_frame_deltas(archive, rows)  # single physical layer; counter advances pre -> post
    add_boundary_times(archive, rows)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', type=Path, metavar='ARCHIVE')
    ap.add_argument('frames_csv', type=Path, nargs='?', metavar='frames.csv', help='default: ARCHIVE/frames.csv')
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv or args.archive / 'frames.csv')
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(f'R47 bracket blocked: {exc}')
    if not rows:
        ap.exit(0, 'R47: no optical windows in archive; no CSV emitted\n')
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
