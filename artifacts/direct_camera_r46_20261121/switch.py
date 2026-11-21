#!/usr/bin/env python3
"""python3 switch.py ARCHIVE > switch.csv — passive OEM dispatch per TAG.klog.

Use the R44_TAG_BEGIN/END envelopes, including for R46 tag names. A match
is an entire contiguous array (type, link mode, declared size, payload), not
a shared prefix, an Android request, an active SF mode or a DDIC readback.
R35 windows.csv independently identifies ordinary HWC 0/120 (group 0x3)
and 1/144 (0x1). In selected_boe_v4 these are timing@0 and @1; @6/@7 also
advertise nominal 120 but are special idle-10/1, not ordinary 120. Compare
all eight *timing-switch-command* arrays and the two distinct R44 DC arrays.
Every exact range is listed, including coincident DT matches if ambiguous.
requested_mode is from the MODE_TRACE acquisition receipt (p = preferred
mode plus min/peak). Optional .capture signed return histograms apply to the
whole tagged trace interval; they are not paired with particular writes.

dcs51_tx records DCS writes whose opcode is 51, with the last observed page
selector, not every payload containing byte 51. Only page 00 + a two-byte
operand qualifies for page00_dbv_tx. It is a commanded value, not a measured
brightness or proof of a change. Page context is never imported from another
tag. Blank counts mean unqualified bracket; zero counts cover this log only.
"""

import argparse
from collections import defaultdict
import csv
from decimal import Decimal
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import dispatch as r44


def references():
    refs = r44.references()
    if refs['off'] == refs['on']:
        raise ValueError('DC OFF and ON controls are indistinguishable')
    labels = {'off': 'DC_OFF', 'on': 'DC_ON'}
    timings = r44.PANEL / 'qcom,mdss-dsi-display-timings'
    prop = 'qcom,mdss-dsi-timing-switch-command'
    nodes = sorted(timings.glob('timing@*'))
    if [p.name for p in nodes] != [f'timing@{i}' for i in range(8)]:
        raise ValueError('incomplete selected BOE v4 timing inventory')
    for node in nodes:
        hz = int.from_bytes((node / 'qcom,mdss-dsi-panel-framerate').read_bytes(), 'big')
        idle = list(node.glob('qcom,framerate-group-special-idle-*'))
        if len(idle) > 1 or (node / (prop + '-state')).read_bytes().rstrip(b'\0') != b'dsi_lp_mode':
            raise ValueError(f'{node.name}: unexpected group or timing-switch state')
        mode = 'idle-' + idle[0].name.split('special-idle-')[1] if idle else f'{hz}hz'
        labels[node.name] = f'{node.name}/{mode}'
        refs[node.name] = []
        for p in r44.parse_packets((node / prop).read_bytes()):
            h = bytes.fromhex(p['header'])
            refs[node.name].append((int.from_bytes(h[5:7], 'big'), h[0], 'lp', bytes.fromhex(p['payload'])))
        if not refs[node.name]:
            raise ValueError(f'{node.name}: empty {prop}')
    if labels['timing@0'] != 'timing@0/120hz' or labels['timing@1'] != 'timing@1/144hz':
        raise ValueError('ordinary timing nodes do not agree with selected BOE v4 controls')
    return refs, labels


def page_writes(tag, lines):
    # Only called after r44.summarize has validated uniqueness/order/timestamps.
    active = False
    page = selector = None
    tx = 0
    raw, dbv = [], []
    for line in lines:
        marker = r44.MARK.fullmatch(line)
        if marker and marker[2] == tag:
            if marker[3] == 'END':
                break
            active = True
            continue
        if not active:
            continue
        ctrl = r44.CTRL.search(line)
        if not ctrl:
            if r44.LOSS.search(line):
                page = selector = None
            continue
        tx += 1
        body = r44.BODY.fullmatch(line[ctrl.end():].rstrip())
        if not body or ctrl[1] != '1':
            page = selector = None
            continue
        payload = bytes.fromhex(body[4])
        dtype = int(body[2], 16)
        if len(payload) != int(body[1]) or not payload:
            page = selector = None
        elif dtype == 0x39 and len(payload) == 4 and payload[:3] == b'\xff\x5a\xa5':
            page, selector = payload[3], tx
        elif dtype not in (0x05, 0x15, 0x39) or payload[0] in (0xff, 0x01, 0x10, 0x11):
            # Unknown transfer semantics, unrecognised selector, reset/sleep.
            page = selector = None
        elif payload[0] == 0x51:
            ctx = '?' if page is None else f'{page:02x}@tx{selector}'
            raw.append(f'tx{tx} page={ctx} type=0x{dtype:02x} {body[3]} {payload.hex(" ")}')
            if page == 0 and dtype == 0x39 and len(payload) == 3:
                dbv.append(f'tx{tx}={int.from_bytes(payload[1:], "big")}')
    return len(raw), '; '.join(raw), len(dbv), '; '.join(dbv)


def summarize(tag, lines, refs, labels):
    r = r44.summarize(tag, lines, refs)
    row = {k: r[k] for k in ('tag', 'bracket', 'begin_s', 'end_s', 'observed_tx', 'invalid_tx',
                              'loss_notices', 'tx_issues')}
    row.update(exact_120=r.get('exact_timing@0'), exact_144=r.get('exact_timing@1'),
               exact_dc_off=r['exact_off'], exact_dc_on=r['exact_on'], exact_sets=None,
               ambiguous_exact=None, dcs51_count=None, dcs51_tx=None, page00_dbv_count=None, page00_dbv_tx=None)
    if r['bracket'] != 'ok':
        return row

    # R44 exact-hit details (unlike near-match diagnostics) are one 'tx N-M'
    # per contiguous match. Preserve TX order, repetitions and alternative IDs.
    ranges = defaultdict(list)
    for key in refs:
        if r['exact_' + key]:
            for span in r[key + '_detail'].split('; '):
                a, b = map(int, span.removeprefix('tx ').split('-'))
                ranges[a, b].append(labels[key])
    def spans(ambiguous_only):
        return '; '.join(f'tx{a}-{b} {"|".join(ids)}' for (a, b), ids in sorted(ranges.items())
                         if not ambiguous_only or len(ids) > 1)
    row['exact_sets'], row['ambiguous_exact'] = spans(False), spans(True)
    row['dcs51_count'], row['dcs51_tx'], row['page00_dbv_count'], row['page00_dbv_tx'] = page_writes(tag, lines)
    return row


def receipts(archive):
    requests = {}
    path = archive / 'acquisition.log'
    for line in path.read_text().splitlines() if path.exists() else ():
        if not line.startswith('MODE_TRACE '):
            continue
        match = re.fullmatch(r'MODE_TRACE (\w+) requested=(p?(?:120|144)) txlines=(\d+)', line)
        if not match or match[1] in requests:
            raise ValueError(f'{path.name}: malformed or duplicate MODE_TRACE: {line}')
        requests[match[1]] = match[2], int(match[3])
    return requests


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    args = ap.parse_args()
    try:
        paths = sorted(args.archive.glob('*.klog'))
        if not paths:
            raise ValueError('no passive TAG.klog files in ARCHIVE')
        refs, labels = references()
        requests = receipts(args.archive)
        missing = requests.keys() - {p.stem for p in paths}
        if missing:
            raise ValueError(f'missing requested-mode klogs: {sorted(missing)}')
        rows = []
        for p in paths:
            lines = p.read_text(errors='replace').splitlines()
            row = summarize(p.stem, lines, refs, labels)
            requested, n = requests.get(p.stem, (None, None))
            if requested and row['bracket'] == 'ok' and n != row['observed_tx']:
                raise ValueError(f'{p.name}: TX count differs from MODE_TRACE receipt')
            row['requested_mode'] = requested
            capture = p.with_suffix('.capture')
            trace = r44.trace_summary(row, lines, capture.read_text(errors='replace').splitlines()
                                      if capture.exists() else None)
            for key in ('trace_status', 'ctrl_rc_hist', 'param_rc_hist'):
                row[key] = trace[key]
            rows.append(row)
        rows.sort(key=lambda row: (Decimal(row['begin_s'] or 'Infinity'), row['tag']))
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


if __name__ == '__main__':
    main()
