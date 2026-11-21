#!/usr/bin/env python3
"""python3 dispatch.py ARCHIVE > dispatch.csv — one row per R44_TAG printk envelope.

An exact TX array matches type, link mode, declared length and all bytes on
ctrl-1 in order. APL ON/OFF are LP; their payloads alone are also the first
4/3 packets of HBM ON/OFF (HS). HS prefixes are reported separately, even
when the HBM suffix is missing. The logger does not expose DT batch flags.
Page-00 DBVs require a selector in this envelope; they are commanded values.

The sibling .capture has independent trace markers. r47_apl is a function
ENTRY (unsigned input level); only r47_send has the MOT sender's signed rc.
Its return site identifies the caller. Counts refer to the marked interval;
profile hits/misses cover the entire probe lifetime. Blank counts mean no
qualified window/probe. OEM threshold/state/level lines are software reports.
None of these observations acknowledge individual packets or read back DDIC state.
"""

import argparse
from collections import Counter
import csv
from decimal import Decimal
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import dispatch as r44
from direct_camera_r46_20261121.switch import page_writes


def references():
    refs = {}
    for side, n in (('on', 4), ('off', 3)):
        for name, stem, count, state in ((side, 'panel-apl', n, None),
                                         ('hbm_' + side, 'hbm', n + 1, b'dsi_hs_mode\0')):
            prop = f'qcom,mdss-dsi-{stem}-{side}-command'
            path = r44.PANEL / (prop + '-state')
            if (path.read_bytes() if path.exists() else None) != state:
                raise ValueError(f'{prop}: unexpected selected BOE v4 state')
            # Pinned Motorola dsi_panel.c:6115-6125 uses parse_cmd_sets_sub;
            # 3726-3731 default missing state to LP; 1176-1179 apply USE_LPM.
            mode = 'lp' if state is None else 'hs'
            seq = []
            for p in r44.parse_packets((r44.PANEL / prop).read_bytes()):
                h = bytes.fromhex(p['header'])
                seq.append((int.from_bytes(h[5:7], 'big'), h[0], mode, bytes.fromhex(p['payload'])))
            if len(seq) != count or any(dtype != 0x39 for _, dtype, _, _ in seq):
                raise ValueError(f'{prop}: unexpected selected BOE v4 packet count/type')
            refs[name] = seq
        hs_prefix = [(nbytes, dtype, 'hs', data) for nbytes, dtype, _, data in refs[side]]
        if hs_prefix != refs['hbm_' + side][:-1]:
            raise ValueError(f'HBM {side}: not the expected overlapping payload prefix')
        refs['prefix_' + side] = hs_prefix
    return refs


OEM = re.compile(r'\bapl config apl_config\.apl_threshold\s*=\s*(\d+)\s+'
                 r'apl_config\.apl_state\s*=\s*([01])\s*,\s*bl_lvl\s*=\s*(\d+)\s*$')


def hits(summary, name):
    # r44.matches emits one 1-based inclusive 'tx N-M' range per exact hit.
    if not summary['exact_' + name]:
        return []
    return [tuple(map(int, span.removeprefix('tx ').split('-'))) for span in summary[name + '_detail'].split('; ')]


def summarize(tag, klog, refs):
    s = r44.summarize(tag, klog, refs)
    row = {k: s[k] for k in ('tag', 'bracket', 'begin_s', 'end_s', 'observed_tx',
                             'invalid_tx', 'loss_notices', 'tx_issues')}
    for side in ('on', 'off'):
        for key in ('exact_apl_', 'exact_hbm_', 'hs_prefix_only_'):
            row[key + side] = None
    row.update(exact_sets=None, shared_hs_prefixes=None, dcs51_count=None, dcs51_tx=None,
               page00_dbv_count=None, page00_dbv_tx=None, oem_apl_count=None, oem_apl_config=None)
    if s['bracket'] != 'ok':
        return row

    exact, prefixes = [], []
    for side in ('on', 'off'):
        hbm = hits(s, 'hbm_' + side)
        for family, spans in (('apl', hits(s, side)), ('hbm', hbm)):
            row['exact_' + family + '_' + side] = len(spans)
            exact.extend((a, b, (family + '_' + side).upper()) for a, b in spans)
        only = 0
        for a, b in hits(s, 'prefix_' + side):
            full = (a, b + 1) in hbm
            only += not full
            prefixes.append((a, b, f'HBM_{side.upper()} ' + ('with suffix' if full else 'prefix only; no exact set')))
        row['hs_prefix_only_' + side] = only

    def render(spans):
        return '; '.join(f'tx{a}-{b} {label}' for a, b, label in sorted(spans))

    row['exact_sets'], row['shared_hs_prefixes'] = render(exact), render(prefixes)
    row['dcs51_count'], row['dcs51_tx'], row['page00_dbv_count'], row['page00_dbv_tx'] = page_writes(tag, klog)
    configs = []
    active = False
    for line in klog:
        marker = r44.MARK.fullmatch(line)
        if marker and marker[2] == tag:
            if marker[3] == 'END':
                break
            active = True
        elif active and (m := OEM.search(line)):
            configs.append(f'threshold={m[1]} state={m[2]} bl_lvl={m[3]}')
    row.update(oem_apl_count=len(configs), oem_apl_config='; '.join(configs))
    return row


BASE = {'r44_ctrl': 'dsi_ctrl_cmd_transfer', 'r44_param': 'dsi_panel_send_param_cmd'}
EXTRA = {'r47_apl': 'dsi_panel_set_apl', 'r47_send': 'dsi_panel_tx_send_mot_cmd'}
PROBES = {**BASE, **EXTRA}
SITE = r'(?:\+0x[\da-fA-F]+(?:/0x[\da-fA-F]+)?)?(?: \[\w+\])?'


def probe_value(event, body):
    """Return (value, caller symbol); never interpret an APL entry as a return."""
    func = PROBES[event] + SITE
    if event == 'r47_apl':
        m = re.fullmatch(r'\(' + func + r'\)\s+level=(0x[\da-fA-F]+|\d+)', body)
        if m:
            level = int(m[1], 16 if m[1].startswith('0x') else 10)
            if level < 2**32:
                return level, None
    else:
        m = re.fullmatch(r'\(([^\s()+]+)' + SITE + r' <- ' + func + r'\)\s+rc=([+-]?\d+)', body)
        if m and -2**31 <= int(m[2]) < 2**31:
            return int(m[2]), m[1]
    raise ValueError('invalid ' + event + ' record')


def hist(values):
    return ' '.join(f'{k}:{v}' for k, v in sorted(Counter(values).items()))


def trace_summary(tag, klog, capture):
    out = dict(trace_status='absent', trace_entries_in_buffer=None, trace_entries_written=None)
    for event in PROBES:
        out[event + '_profile_hits'] = out[event + '_profile_missed'] = None
    out.update(ctrl_rc_hist=None, param_rc_hist=None, apl_entries=None, apl_levels=None,
               send_returns=None, send_rc_hist=None, send_callers=None, apl_send_returns=None,
               apl_send_rc_hist=None, apl_trace_events=None)
    if capture is None:
        return out
    sections = ['R44_KLOG', 'R44_TRACE', 'R44_PROFILE', 'R44_TRACE_RETURN']
    if [line for line in capture if line in sections] != sections or capture[-1] != sections[-1]:
        out['trace_status'] = 'missing, duplicate or misplaced capture section/return marker'
        return out
    a, b, c, d = map(capture.index, sections)
    trace = capture[b+1:c]
    issues = []
    if capture[a+1:b] != klog:
        issues.append('embedded KLOG differs from TAG.klog')
    headers = [m.groups() for line in trace if (m := r44.TRACE_HEADER.fullmatch(line))]
    if len(headers) == 1:
        stored, written = map(int, headers[0])
        out.update(trace_entries_in_buffer=stored, trace_entries_written=written)
        if stored != written:
            issues.append('trace buffer overrun')
    else:
        issues.append('missing or duplicate buffer header')

    events = []
    for line in trace:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = r44.TRACE_EVENT.search(line)
        if not m:
            issues.append('unparsed trace record or loss notice')
            continue
        ts, name, body = m.groups()
        caller, value = None, None
        if name == 'tracing_mark_write':
            value = body
        elif name in PROBES:
            try:
                value, caller = probe_value(name, body)
            except ValueError as exc:
                issues.append(str(exc))
        else:
            issues.append('unexpected trace event: ' + name)
        events.append((Decimal(ts), name, value, caller))
    if out['trace_entries_in_buffer'] != len(events):
        issues.append('buffer count differs from decoded entries')

    seen = set()
    totals = Counter(name for _, name, _, _ in events)
    for line in capture[c+1:d]:
        if not line.strip():
            continue
        m = re.fullmatch(r'\s*(\w+)\s+(\d+)\s+(\d+)\s*', line)
        if not m or m[1] not in PROBES or m[1] in seen:
            issues.append('unexpected, malformed or duplicate profile row')
            continue
        name, hits, missed = m[1], int(m[2]), int(m[3])
        seen.add(name)
        out[name + '_profile_hits'], out[name + '_profile_missed'] = hits, missed
        if hits != totals[name] or missed:
            issues.append(name + ' profile misses or hit count mismatch')
    if (set(BASE) | (totals.keys() & PROBES.keys())) - seen:
        issues.append('missing probe profile')

    marks = [(i, ts, val) for i, (ts, name, val, _) in enumerate(events) if name == 'tracing_mark_write']
    if [val for _, _, val in marks] != [f'R44_{tag}_BEGIN', f'R44_{tag}_END']:
        issues.append('missing, extra or reversed trace markers')
    else:
        (first, start, _), (last, end, _) = marks
        window = events[first+1:last]
        if start > end or any(not start <= ts <= end for ts, *_ in window):
            issues.append('event timestamp outside trace markers or reversed timestamps')
    if issues:
        out['trace_status'] = '; '.join(dict.fromkeys(issues))
        return out

    out['trace_status'] = 'ok'
    for name in BASE:
        out[name[4:] + '_rc_hist'] = hist(v for _, e, v, _ in window if e == name)
    if 'r47_apl' in seen:
        levels = [v for _, e, v, _ in window if e == 'r47_apl']
        out.update(apl_entries=len(levels), apl_levels=hist(levels))
    if 'r47_send' in seen:
        sends = [(caller, v) for _, e, v, caller in window if e == 'r47_send']
        apl = [v for caller, v in sends if caller == 'dsi_panel_set_apl']
        out.update(send_returns=len(sends), send_rc_hist=hist(v for _, v in sends),
                   send_callers=hist(c for c, _ in sends), apl_send_returns=len(apl), apl_send_rc_hist=hist(apl))
    if seen & EXTRA.keys():
        details = []
        for ts, event, value, caller in window:
            if event == 'r47_apl':
                details.append(f'{ts} entry level={value}')
            elif event == 'r47_send':
                details.append(f'{ts} send caller={caller} rc={value}')
        out['apl_trace_events'] = '; '.join(details)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('archive', metavar='ARCHIVE', type=Path)
    archive = parser.parse_args().archive
    try:
        refs = references()
        rows = []
        for path in sorted(archive.glob('*.klog')):
            klog = path.read_text(errors='replace').splitlines()
            row = summarize(path.stem, klog, refs)
            capture = path.with_suffix('.capture')
            row.update(trace_summary(path.stem, klog, capture.read_text(errors='replace').splitlines()
                                     if capture.exists() else None))
            rows.append(row)
        if not rows:
            raise ValueError('no TAG.klog files in ARCHIVE')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda r: (Decimal(r['begin_s'] or 'Infinity'), r['tag'])))


if __name__ == '__main__':
    main()
