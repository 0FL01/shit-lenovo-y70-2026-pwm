#!/usr/bin/env python3
"""Bind stock-ON R46 windows: python3 -B windows.py ARCHIVE frames.csv > windows.csv

Bind each physical bracket from its own archive. All three legs of a complete
bracket require CAL 1250 us for brightness and DAY 200/312.5/500 us, with
identical shutter inventories. An optional cal_{leg}_4000 pair is for geometry
only: include it in all three legs or none. It does not replace CAL 1250 us.

Exit 0: complete 120A/144B/120C bracket at the recorded boundaries. Exit 3:
only valid 120 Hz windows were bound; the CSV explicitly marks the bracket
blocked. Invalid evidence exits 2 without CSV. video_frame_delta is post minus
pre on the same physical video layer; the next pre must not precede that post.
These boundary samples do not prove uninterrupted playback or measure fps.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121 import state, windows as r43
from direct_camera_r44_20261121 import windows as r44


MODES = {'on120A': (0, 120), 'on144B': (1, 144), 'on120C': (0, 120)}
REQUIRED = {('cal', '1250'), ('day', '200'), ('day', '312'), ('day', '500')}
BLOCKED = 'BLOCKED_NO_VERIFIED_144_WINDOW'


def video_sample(sf):
    """Resolve a visible composition-list counter to R44's sole current SDM video."""
    sdm = state.block(sf, r'^SDM3 display_id: 0[ \t]*\n', r'^(?:SDM3 display_id:|OverlayProperties:)')
    seq = str(r44.current_surface_id(sdm))
    ident = state.value(sf, r'^Display (\d+) \(HWC display 0\):')
    physical = state.physical(sf, ident)
    names = re.findall(rf'^ *- Output Layer 0x[0-9a-f]+\(({r43.SURFACE})\)[ \t]*$', physical, re.M)
    names = [name for name in names if name.rsplit('#', 1)[1] == seq]
    r43.require(len(names) == 1, 'expected one matching physical video output')
    name, = names
    stack = state.value(physical, r'^ +layerFilter=\{layerStack=(\d+) toInternalDisplay=true *\}[ \t]*$')
    r43.require(stack is not None, 'missing or ambiguous physical layer stack')
    composition = state.block(sf, r'^Composition list \(bottom to top\)[ \t]*\n', r'^Input list\b')
    layers = state.block(composition, rf'^LayerStack={stack}[ \t]*\n', r'^\S').splitlines()
    # Require the same full output name AND sequence in the bracketed Layer ID.
    # Count headers before reading visibility, so a malformed duplicate fails.
    matches = []
    for i, line in enumerate(layers):
        h = re.fullmatch(r'[ \t]+Layer \[([0-9]+)\] (.+)', line)
        if h and (h[1] == seq or h[2] == name):
            r43.require(h.groups() == (seq, name), 'composition layer identity mismatch')
            matches.append(i)
    r43.require(len(matches) == 1, 'missing or ambiguous composition video layer')
    i = matches[0] + 1
    detail = layers[i] if i < len(layers) else ''
    frame = re.match(r'[ \t]+visible reason=[ \t]+buffer=[1-9][0-9]* frame=([0-9]+)(?:[ \t]|$)', detail)
    r43.require(frame and detail.count('frame=') == 1, 'missing or ambiguous visible video frame counter')
    return name, int(frame[1])


def add_frame_deltas(archive, rows):
    # Only the receipt-ordered windows of this clip. Independent pilot dumps
    # have their own counter origins and must not seed the first comparison.
    previous = None
    for row in rows:
        phase = row['phase']
        samples = []
        for side in ('pre', 'post'):
            path = archive / f'{phase}-{side}.sf'
            try:
                samples.append(video_sample(r43.original(path).read_text()))
            except ValueError as exc:
                raise ValueError(f'{path.name}: {exc}') from None
        (name, pre), (post_name, post) = samples
        r43.require(name == post_name and (previous is None or previous[0] == name),
                    f'{phase}: physical video layer changed')
        r43.require(post > pre, f'{phase}: video frame counter did not advance across window')
        r43.require(previous is None or pre >= previous[1], f'{phase}: video frame counter regressed between windows')
        row['video_frame_delta'] = post - pre
        previous = (name, post)


def bind(archive, frames_csv):
    # R44 recognizes 'on' before the digits, binds both actual DC reads to it,
    # and puts all of these CAL/DAY labels in a single surface-ID comparison.
    rows = r44.bind(archive, frames_csv)
    order, observed = [], {}
    for row in rows:  # receipt order
        phase = row['phase']
        m = re.fullmatch(r'(cal|day)_(on120A|on144B|on120C)_([0-9]+)', phase)
        if not m or (m[1] == 'cal' and m[3] not in ('1250', '4000')):
            raise ValueError(f'{phase}: unexpected R46 phase')
        group, leg, shutter = m.groups()  # R43 already verified shutter vs DNG and receipt
        if (group, shutter) == ('cal', '4000') and row['frames'] != 2:
            raise ValueError(f'{phase}: expected a 4000 us geometry CAL pair')
        if not order or order[-1] != leg:
            order.append(leg)
        observed.setdefault(leg, set()).add((group, shutter))
        if (row['dc_label'], row['sysfs_bl'], row['scene'], row['hdr_mode'], row['hbm_mode']) != (
                'on', 3593, 'hdr', 'HBM_HDR', 'hdr'):
            raise ValueError(f'{phase}: expected stock ON, BL 3593 and actual HDR HBM')
        hwc, hz = MODES[leg]
        if (row['hwc_id'], row['sf_refresh_hz'], row['sdm_config'], row['sdm_fps']) != (hwc, hz, hwc, hz):
            raise ValueError(f'{phase}: expected actual SF/SDM HWC {hwc} at {hz} Hz')
        if not row['same_surface_at_boundaries']:
            raise ValueError(f'{phase}: video SurfaceView changed between R46 boundaries')
        row['refresh_leg'] = leg

    if order in (['on120A'], ['on120A', 'on120C']):
        status = BLOCKED
    elif order == list(MODES):
        for leg in order:
            missing = REQUIRED - observed[leg]
            if missing:
                raise ValueError(f'{leg}: missing required windows {sorted(missing)}')
            if observed[leg] != observed['on120A']:
                raise ValueError(f'{leg}: shutter inventory differs from on120A')
        status = 'BOUND_120_144_120_AT_BOUNDARIES'
    else:
        raise ValueError(f'expected ordered 120A/144B/120C bracket; observed {order}')
    add_frame_deltas(archive, rows)
    for row in rows:
        row['bracket_status'] = status
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(f'R46 bracket blocked: {exc}')
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)
    if rows[0]['bracket_status'] == BLOCKED:
        ap.exit(3, f'{BLOCKED}: only bound 120 Hz windows were written\n')


if __name__ == '__main__':
    main()
