#!/usr/bin/env python3
"""python dispatch.py ARCHIVE > dispatch.csv — outgoing dispatch and optional return trace.

One row per TAG.klog, bounded by the unique R44_TAG_BEGIN/END printk messages.
An exact set is a contiguous run of ctrl-1 TX records matching the live-DT
packet type, link mode, declared length and every payload byte, in order. This
logger does not report every DT header field, a transfer return, or panel state.
Counts are observations within the markers; blank means no qualified bracket.
All packet positions in diagnostics are 1-based (inclusive).

With a sibling TAG.capture, *_returns and *_rc* count signed function returns
strictly between the two trace markers. Profile hits/misses cover the whole
probe lifetime, not just that interval. R44_TRACE_RETURN is observe.sh's final
cleanup marker. Correlation means co-observation by tag, never packet-to-return
pairing, acknowledged bytes, or DDIC readback.
"""

import argparse
from collections import Counter
import csv
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / 'artifacts/device_tree/selected_boe_v4'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets


# printk format as in artifacts/stock_base_rates_20261107/analyze.py, but
# consume the whole payload: a malformed/truncated TX must not disappear.
STAMP = r'\[\s*(\d+(?:\.\d+)?)\]'
MARK = re.compile(rf'^(?:<\d+>)?(?:{STAMP}\s*)?(?:\[\s*[TC]\s*\d+\]\s*)?'
                  r'R44_(\S+)_(BEGIN|END)\s*$')
CTRL = re.compile(r'\bdsi-ctrl-(\d+):\s+dsi_ctrl_cmd_transfer\b')
BODY = re.compile(r'\s+len=(\d+), type=0x([\da-fA-F]+) (hs|lp) cmds=\s*'
                  r'((?:[\da-fA-F]{2}(?:[ \t]+|$))*)')
LOSS = re.compile(r'\b(?:\d+ (?:messages|events) (?:dropped|lost)|LOST \d+ EVENTS)\b', re.I)
TRACE_HEADER = re.compile(r'# entries-in-buffer/entries-written:\s*(\d+)/(\d+)\s+#P:\d+\s*')
TRACE_EVENT = re.compile(r'\[\d+\]\s+\S+\s+(\d+\.\d+):\s+(\w+):\s*(.*?)\s*$')
PROBES = {'ctrl': 'dsi_ctrl_cmd_transfer', 'param': 'dsi_panel_send_param_cmd'}


def references():
    refs = {}
    for name in ('on', 'off'):
        prop = 'qcom,mdss-dsi-dc-' + name + '-command'
        blob = (PANEL / prop).read_bytes()
        if (PANEL / (prop + '-state')).read_bytes().rstrip(b'\0') != b'dsi_hs_mode':
            raise ValueError(f'{prop}: unexpected archived command state')
        seq = []
        for p in parse_packets(blob):
            header = bytes.fromhex(p['header'])
            seq.append((int.from_bytes(header[5:7], 'big'), header[0], 'hs', bytes.fromhex(p['payload'])))
        if len(blob) != 875 or len(seq) != 75:
            raise ValueError(f'{prop}: not the selected BOE v4 875-byte / 75-packet archive')
        refs[name] = seq
    return refs


def describe(p):
    if p is None:
        return 'unusable record or log gap'
    size, dtype, mode, payload = p
    return f'len={size} type=0x{dtype:02x} {mode} {payload.hex(" ")}'


def matches(observed, reference, ordinals):
    n = len(reference)
    hits = [i for i, p in enumerate(observed) if p == reference[0] and observed[i:i+n] == reference]
    if hits:
        return len(hits), '; '.join(f'tx {ordinals[i]}-{ordinals[i+n-1]}' for i in hits)
    # A missing beginning is as important as a truncated tail. Report the
    # longest contiguous fragment, not an edit-distance score or a near hit.
    i, j, k = SequenceMatcher(None, observed, reference, autojunk=False).find_longest_match()
    if not k:
        return 0, f'no matching packet (0/{n})'
    detail = f'best {k}/{n}: tx {ordinals[i]}-{ordinals[i+k-1]} = DT {j+1}-{j+k}'
    for pos, refpos in ((i-1, j-1), (i+k, j+k)):
        if 0 <= refpos < n:
            actual = describe(observed[pos]) if 0 <= pos < len(observed) else 'window boundary'
            detail += f'; DT {refpos+1} expects {describe(reference[refpos])}, saw {actual}'
    return 0, detail


def summarize(tag, lines, refs):
    marks = [(i, *m.groups()) for i, line in enumerate(lines) if (m := MARK.fullmatch(line))]
    begins, ends = ([m for m in marks if m[2:] == (tag, side)] for side in ('BEGIN', 'END'))
    start = begins[0][1] if len(begins) == 1 else None
    end = ends[0][1] if len(ends) == 1 else None
    row = dict(tag=tag, bracket='ok', begin_s=start, end_s=end, observed_tx=None,
               tx_declared_lengths=None, invalid_tx=None, loss_notices=None, tx_issues=None,
               dt_packets=len(refs['on']), exact_on=None, exact_off=None, on_detail=None, off_detail=None)
    if len(begins) != 1 or len(ends) != 1:
        row['bracket'] = f'BEGIN={len(begins)} END={len(ends)}'
    elif begins[0][0] >= ends[0][0]:
        row['bracket'] = 'END before BEGIN'
    elif not start or not end or Decimal(start) > Decimal(end):
        row['bracket'] = 'missing or reversed marker timestamp'
    elif any(begins[0][0] < m[0] < ends[0][0] for m in marks):
        row['bracket'] = 'interleaved markers'
    if row['bracket'] != 'ok':
        return row

    observed, ordinals, issues = [], [], []
    tx = invalid = gaps = 0
    lengths = Counter()
    for line in lines[begins[0][0]+1:ends[0][0]]:
        ctrl = CTRL.search(line)
        if not ctrl:
            if LOSS.search(line):
                gaps += 1
                observed.append(None)  # never join across a reported hole
                ordinals.append(None)
            continue
        tx += 1
        packet = None
        body = line[ctrl.end():]
        declared = re.match(r'\s+len=(\d+)\b', body)
        lengths[int(declared[1]) if declared else '?'] += 1
        m = BODY.fullmatch(body.rstrip())
        if ctrl[1] != '1':
            reason = f'unexpected ctrl-{ctrl[1]}'
        elif not m:
            reason = 'malformed record'
        else:
            size, dtype, mode, payload = int(m[1]), int(m[2], 16), m[3], bytes.fromhex(m[4])
            if size == len(payload):
                packet = size, dtype, mode, payload
            else:
                reason = f'declared {size} bytes, logged {len(payload)}'
        if packet is None:
            invalid += 1
            if len(issues) < 4:
                issues.append(f'tx {tx}: {reason}')
        observed.append(packet)
        ordinals.append(tx)
    row.update(observed_tx=tx, invalid_tx=invalid, loss_notices=gaps, tx_issues='; '.join(issues),
               tx_declared_lengths=' '.join(f'{k}:{lengths[k]}' for k in sorted(lengths, key=lambda k: -1 if k == '?' else k)))
    for name, reference in refs.items():
        row['exact_'+name], row[name+'_detail'] = matches(observed, reference, ordinals)
    return row


def trace_summary(row, klog, capture):
    out = dict(trace_status='absent', trace_return_marker=None, trace_begin_s=None, trace_end_s=None,
               trace_entries_in_buffer=None, trace_entries_written=None)
    for probe in PROBES:
        for field in ('returns', 'rc0', 'nonzero', 'rc_hist', 'profile_hits', 'profile_missed'):
            out[f'{probe}_{field}'] = None
    out.update(ctrl_minus_observed_tx=None, correlation='not qualified')
    if capture is None:
        return out

    issues = []
    sections = ['R44_KLOG', 'R44_TRACE', 'R44_PROFILE']
    labels = [line for line in capture if line in sections or line == 'R44_TRACE_RETURN']
    returned = labels == sections + ['R44_TRACE_RETURN'] and capture[-1] == 'R44_TRACE_RETURN'
    out['trace_return_marker'] = int(returned)
    if not returned:
        issues.append('missing or misplaced R44_TRACE_RETURN')
    if [label for label in labels if label in sections] != sections:
        out['trace_status'] = 'missing, duplicate or unordered capture sections'
        return out
    a, b, c = map(capture.index, sections)
    if klog != capture[a+1:b]:
        issues.append('embedded KLOG differs from TAG.klog')
    trace = capture[b+1:c]
    profile = capture[c+1:-1] if returned else capture[c+1:]
    headers = [m for line in trace if (m := TRACE_HEADER.fullmatch(line))]
    if len(headers) == 1:
        stored, written = map(int, headers[0].groups())
        out.update(trace_entries_in_buffer=stored, trace_entries_written=written)
        if stored != written:
            issues.append('trace buffer overrun')
    else:
        issues.append('missing or duplicate buffer header')

    # Profile totals may include events outside the trace_marker pair. Count
    # the whole trace for reconciliation, and the actual interval separately.
    events = []
    for line in trace:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = TRACE_EVENT.search(line)
        if not m:
            issues.append('unparsed trace record or loss notice')
            continue
        ts, event, body = m.groups()
        val = None
        if event.startswith('r44_') and event[4:] in PROBES:
            rc = re.fullmatch(r'\(.*<- ' + PROBES[event[4:]] + r'\)\s+rc=([+-]?\d+)', body)
            if rc and -(2**31) <= int(rc[1]) < 2**31:
                val = int(rc[1])
            else:
                issues.append('invalid signed return: ' + event)
        elif event != 'tracing_mark_write':
            issues.append('unexpected trace event')
        events.append((ts, event, body, val))
    if out['trace_entries_in_buffer'] != len(events):
        issues.append('buffer count differs from decoded entries')
    markers = [(i, ts, body) for i, (ts, event, body, _) in enumerate(events) if event == 'tracing_mark_write']
    pair = [f'R44_{row["tag"]}_{side}' for side in ('BEGIN', 'END')]
    bounded = [m[2] for m in markers] == pair and Decimal(markers[0][1]) <= Decimal(markers[1][1])
    if bounded:
        (first, start, _), (last, end, _) = markers
        out.update(trace_begin_s=start, trace_end_s=end)
        window = events[first+1:last]
        if any(not Decimal(start) <= Decimal(ts) <= Decimal(end) for ts, *_ in window):
            issues.append('event timestamp outside trace markers')
    else:
        issues.append('missing, extra or reversed trace markers')
    for probe in PROBES:
        event = 'r44_' + probe
        profiles = [m for line in profile if (m := re.fullmatch(r'\s*'+event+r'\s+(\d+)\s+(\d+)\s*', line))]
        if len(profiles) == 1:
            hits, missed = map(int, profiles[0].groups())
            out[probe+'_profile_hits'], out[probe+'_profile_missed'] = hits, missed
            if missed or hits != sum(e == event for _, e, _, _ in events):
                issues.append(probe+' profile misses or hit count mismatch')
        else:
            issues.append(probe+' profile row missing or duplicate')
        if bounded:
            values = [v for _, e, _, v in window if e == event]
            if None not in values:
                hist = Counter(values)
                out[probe+'_returns'] = len(values)
                out[probe+'_rc0'] = hist[0]
                out[probe+'_nonzero'] = len(values) - hist[0]
                out[probe+'_rc_hist'] = ' '.join(f'{k}:{hist[k]}' for k in sorted(hist))
    if len([line for line in profile if line.strip()]) != len(PROBES):
        issues.append('expected exactly two profile rows')
    out['trace_status'] = '; '.join(dict.fromkeys(issues)) or 'ok'
    if not issues and row['bracket'] == 'ok' and not (row['invalid_tx'] or row['loss_notices']):
        tx, ctrl, param = row['observed_tx'], out['ctrl_returns'], out['param_returns']
        out['ctrl_minus_observed_tx'] = ctrl - tx  # aggregate only; no bijection implied
        observed = [label for present, label in ((tx, 'TX'), (ctrl, 'ctrl returns'), (param, 'param returns')) if present]
        out['correlation'] = (' + '.join(observed) if observed else 'no TX or probe returns') + ' in tagged intervals'
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    args = ap.parse_args()
    try:
        paths = sorted(args.archive.glob('*.klog'))
        if not paths:
            raise ValueError('no TAG.klog files in archive')
        refs = references()
        rows = []
        for p in paths:
            klog = p.read_text(errors='replace').splitlines()
            row = summarize(p.stem, klog, refs)
            capture = p.with_suffix('.capture')
            lines = capture.read_text(errors='replace').splitlines() if capture.exists() else None
            row.update(trace_summary(row, klog, lines))
            rows.append(row)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


if __name__ == '__main__':
    main()
