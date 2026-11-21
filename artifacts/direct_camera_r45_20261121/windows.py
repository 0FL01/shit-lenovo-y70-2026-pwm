#!/usr/bin/env python3
"""Bind R45 stock HDR/3593 windows: python3 -B windows.py ARCHIVE frames.csv > windows.csv

R44 binds the full receipt/DNG inventory, both DC reads, wake, thermal state
and the sole visible full-field PQ layer at each boundary. All R45 boundaries
must belong to the same SurfaceView. OFF-only evidence is valid even when
the optical pilot fails. ON and returned OFF require a passing native OFF
pilot. The state sequence describes snapshots, not uninterrupted playback,
command dispatch, DDIC readback or an optically resolved switching effect.
"""

import argparse
import csv
from itertools import groupby
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import windows as r44
from direct_camera_r45_20261121 import pilot


def bind(archive, frames_csv):
    rows = r44.bind(archive, frames_csv)  # chronological receipt order, not filename order
    phases = {intent: set() for intent in ('off', 'on', 'ret')}
    for row in rows:
        phase, intent = row['phase'], row['dc_label']
        match = re.fullmatch(rf'(cal|day)_{intent}Low_(\d+)', phase)
        if not match or match[2] not in (('1250', '500') if match[1] == 'cal' else pilot.SHORT):
            raise ValueError(f'{phase}: unexpected R45 low-drive phase')
        phases[intent].add(match.groups())
        if (row['sysfs_bl'], row['hwc_id'], row['sf_refresh_hz']) != (3593, 0, 120):
            raise ValueError(f'{phase}: expected BL 3593 and HWC 0 at 120 Hz')
        if (row['scene'], row['hdr_mode'], row['hbm_mode']) != ('hdr', 'HBM_HDR', 'hdr'):
            raise ValueError(f'{phase}: expected real HDR with stock HDR brightness policy')
        # Every accepted phase is in R44's single 'low' clip group; this flag
        # compares the observed SurfaceView IDs across all its CAL and DAY rows.
        if not row['same_surface_at_boundaries']:
            raise ValueError(f'{phase}: video SurfaceView changed between R45 windows')

    order = [key for key, _ in groupby(row['dc_label'] for row in rows)]
    if order not in (['off'], ['off', 'on', 'ret']):
        raise ValueError('expected OFF-only windows or an ordered OFF/ON/returned-OFF sequence')
    _, allow = pilot.run(archive / 'frames')
    if len(order) == 3:
        if not allow:
            raise ValueError('ON/return windows without a qualified OFF optical pilot')
        # A clipped CAL may need its own 500 us replacement in just one state.
        required = {('cal', '1250')} | {('day', shutter) for shutter in pilot.SHORT}
        for intent, observed in phases.items():
            if not required <= observed:
                raise ValueError(f'{intent}: missing R45 windows: {sorted(required - observed)}')

    for row in rows:
        row['off_pilot'] = 'ALLOW_ON' if allow else 'HOLD_OFF'
        row['observed_dc_sequence'] = 'off_only' if len(order) == 1 else 'off_on_ret_at_boundaries'
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
