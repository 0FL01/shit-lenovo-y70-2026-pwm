#!/usr/bin/env python3
"""Bind R48 SDR windows: python3 -B windows.py ARCHIVE frames.csv > windows.csv

Both boundaries must show stock Flicker prevention OFF, normal SDR at 120 Hz,
and the leg's exact sysfs BL on the same playing full-screen BT.709 surface.
CAL/312 (312.5 us) ascends A/B/C/D; a full CAL/200 fallback is optional.
Each DAY shutter (125/200/312) ascends A/B/C/D then descends Dr/Cr/Br/Ar
in separate excursions. DAY/125 also needs the separate Bs/Q sham pair.
Each window needs four original RAWs. Each excursion closes at BL 6692.
guard_group identifies this receipt, not a shared guard across the D/Dr reset.
BL and frame counters are boundary samples, not continuous telemetry or DDIC
readbacks. Invalid or incomplete archives exit 2 before writing any CSV.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121 import state, windows as r43
from direct_camera_r44_20261121 import windows as r44
from direct_camera_r46_20261121 import windows as r46


DBV = {'A': 14055, 'B': 14056, 'C': 14057, 'D': 14058, 'Bs': 14056, 'Q': 14056}
ASC = ('A', 'B', 'C', 'D')
DESC = ('Dr', 'Cr', 'Br', 'Ar')
SHAM = ('Bs', 'Q')
NS = {'125': 125000, '200': 200000, '312': 312500}
TX = re.compile(r'TX (\w+) request=(none|0(?:\.\d+)?|1(?:\.0+)?) settled=(\d+)')
SECONDS = r'([0-9]+(?:\.[0-9]+)?)'
EXCURSION = re.compile(rf'EXCURSION (\w+) start={SECONDS} end={SECONDS} limit={SECONDS} return=6692')


def phases(group, token, legs):
    return tuple(f'{group}_off{leg}_{token}' for leg in legs)


BLOCKS = {'cal312': phases('cal', '312', ASC), 'cal200': phases('cal', '200', ASC),
          'repeat125': phases('day', '125', SHAM)}
BLOCKS.update({direction + token: phases('day', token, legs) for token in NS
               for direction, legs in (('up', ASC), ('down', DESC))})
REQUIRED = BLOCKS.keys() - {'cal200'}


def schedule(archive):
    """Bind the ordered PREs between returns; an unordered phase inventory is insufficient."""
    log = archive / 'acquisition.log'
    # Enforce closure, release indices and PRE/POST agreement before using a
    # PRE as a window. Run this cheap protocol check before decoding the RAWs.
    windows = list(r43.read_windows(log))
    allowed = {phase for block in BLOCKS.values() for phase in block}
    for phase, scene, bl, hwc, hz, ns, wake, sizes in windows:
        r43.require(phase in allowed, f'{phase}: unexpected R48 phase')
        _, leg, token = phase.split('_')
        expected = DBV[leg.removeprefix('off').removesuffix('r')]
        r43.require((scene, bl, hwc, hz, ns, len(sizes)) == ('sdr', expected, 0, 120, NS[token], 4),
                    f'{phase}: expected SDR, BL {expected}, HWC 0/120, {NS[token]} ns and 4 releases')

    bindings, closed, tx_ids = {}, set(), set()
    members = []
    guard = active = pending = previous_end = deadline = None
    for line in r43.original(log).read_text().splitlines():
        kind = line.split(maxsplit=1)[:1]
        # arm47 prints the target-local token and its absolute deadline. The
        # initial player-launch guard is separate and contains no optical PRE.
        arm = re.fullmatch(r'(\w+) (\d+)', line)
        if arm:
            r43.require(guard is None, f'overlapping or renewed guard: {line}')
            if arm[1] in BLOCKS:
                r43.require(arm[1] not in closed, f'reused guard: {arm[1]}')
                guard, deadline = arm[1], int(arm[2])
        elif kind == ['TX']:
            m = TX.fullmatch(line)
            r43.require(m and active is None and m[1] not in tx_ids, f'invalid or repeated TX: {line}')
            tx_ids.add(m[1])
            if guard:
                r43.require(pending is None and m[2] != 'none', f'{guard}: intervening or missing ordinary request')
                pending = m[1], m[2], int(m[3])
        elif kind == ['PRE']:
            m = r43.PRE.fullmatch(line)  # validated by read_windows
            active = m[1]
            r43.require(guard and len(members) < len(BLOCKS[guard]) and BLOCKS[guard][len(members)] == active,
                        f'{active}: unexpected phase in guard {guard}')
            leg = active.split('_')[1]
            r43.require(pending and pending[0] == f'{guard}_{leg}' and pending[2] == int(m[3]),
                        f'{active}: missing matching TX tag settled at the window BL')
            members.append(active)
            bindings[active] = dict(tx_tag=pending[0], request=pending[1])
            pending = None
        elif kind == ['POST']:
            active = None
        elif kind == ['EXCURSION']:
            m = EXCURSION.fullmatch(line)
            r43.require(m and guard == m[1] and active is None, f'unbound or invalid return receipt: {line}')
            start, end, limit = map(Decimal, m.groups()[1:])
            r43.require(0 < limit <= (47 if guard == 'repeat125' else 83) and
                        deadline - limit <= start < end < deadline and (previous_end is None or start >= previous_end),
                        f'{m[1]}: overlapping or expired excursion')
            r43.require(pending and pending[0] == f'{guard}_down' and pending[2] == 6692,
                        f'{m[1]}: final TX does not return to baseline')
            r43.require(tuple(members) == BLOCKS[guard], f'{guard}: incomplete excursion {members}')
            if guard.startswith('down'):
                r43.require('up' + guard[4:] in closed, f'{guard}: descent precedes ascent')
            elif guard == 'cal200':
                r43.require('cal312' in closed, f'{guard}: fallback precedes CAL/312')
            elif guard == 'repeat125':
                r43.require(Decimal(bindings[members[0]]['request']) == Decimal(bindings[members[1]]['request']),
                            f'{m[1]}: sham requests differ at the same BL')
            for phase in members:
                bindings[phase].update(guard_group=guard, guard_elapsed_s=end-start, guard_limit_s=limit,
                                       guard_return_bl=pending[2])
            closed.add(guard)
            previous_end, guard, pending = end, None, None
            members.clear()
    r43.require(guard is None, f'unclosed optical excursion: {guard}')
    r43.require(REQUIRED <= closed, f'missing required excursions: {sorted(REQUIRED - closed)}')
    return bindings


def video_sample(sf):
    """Check the selected frame's buffer raster, independently of its source crop."""
    name, frame = r46.video_sample(sf)
    sequence = name.rsplit('#', 1)[1]
    composition = state.block(sf, r'^Composition list \(bottom to top\)[ \t]*\n', r'^Input list\b')
    buffers = re.findall(rf'^[ \t]+Layer \[{sequence}\] {re.escape(name)}\n'
                         rf'[ \t]+visible reason=[ \t]+buffer=([1-9][0-9]*) frame={frame}\b',
                         composition, re.M)
    r43.require(len(buffers) == 1, 'missing or ambiguous visible video buffer')
    cache = state.section(sf, 'ClientCache state')
    sizes = re.findall(rf'^[ \t]+ID: {buffers[0]}, size: (.*)$', cache, re.M)
    r43.require(sizes == ['720x1584'], 'current visible video buffer raster is not uniquely 720x1584')
    return name, frame


def check_windows(archive, rows):
    previous = None
    for row in rows:  # R44 returns receipt order
        phase = row['phase']
        r43.require((row['scene'], row['hdr_mode'], row['hbm_mode']) == ('sdr', 'NO_HDR', 'off'),
                    f'{phase}: expected current SDR with HBM off')
        r43.require((row['hwc_id'], row['sf_refresh_hz'], row['sdm_config'], row['sdm_fps']) ==
                    (0, 120, 0, 120), f'{phase}: expected actual SF/SDM HWC 0 at 120 Hz')
        # R44 matches the two actual panelDC/provider reads to the label and the
        # sole visible output to the full SDM video of the receipt's dataspace.
        r43.require(row['dc_label'] == 'off' and row['same_surface_at_boundaries'],
                    f'{phase}: expected stock OFF on a single video surface')
        for side in ('pre', 'post'):
            stem = f'{phase}-{side}'
            session = r43.original(archive / f'{stem}.session').read_text().strip().splitlines()
            r43.require(session == ['inactive', 'stopped: stock registers verified'],
                        f'{stem}: missing verified stock rollback status')
            try:
                name, frame = video_sample(r43.original(archive / f'{stem}.sf').read_text())
            except ValueError as exc:
                raise ValueError(f'{stem}: {exc}') from None
            if previous is not None:
                r43.require(previous[0] == name, f'{stem}: physical SurfaceView changed')
                advanced = frame - previous[1]
                r43.require(advanced > 0 if side == 'post' else advanced >= 0,
                            f'{stem}: nonchronological video frame counter')
                if side == 'post':
                    row['video_frame_delta'] = advanced
            previous = name, frame
        row.update(brightness_leg=phase.split('_')[1], video_raster='720x1584')


def bind(archive, frames_csv):
    bindings = schedule(archive)
    rows = r44.bind(archive, frames_csv)
    r43.require(list(bindings) == [r['phase'] for r in rows], 'bound windows differ from excursion receipts')
    check_windows(archive, rows)
    for row in rows:
        row.update(bindings[row['phase']])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path, metavar='ARCHIVE')
    ap.add_argument('frames_csv', type=Path, metavar='frames.csv')
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(f'R48 windows blocked: {exc}')
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
