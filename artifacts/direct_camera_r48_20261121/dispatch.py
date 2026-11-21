#!/usr/bin/env python3
"""python3 -B dispatch.py ARCHIVE > dispatch.csv — one row per observer tag.

Compare three sysfs brightness samples with the last two-byte 0x51 operand
and the last dsi_panel_set_apl(level) function input. Only an in-tag selector
establishes page 00; agreement of the three values does not establish a page,
a packet acknowledgment, panel readback or optical settling. A repeated setter
may settle with no new probe entry or TX. Entry alone is not APL dispatch.

Order is local to each stream. CTRL counts/returns are aggregate checks, not
paired acknowledgments. Profile hits/misses cover the entire probe lifetime.
An unexpected command family is reported, not filtered out. Integrity errors
produce diagnostic rows and a nonzero exit; absolute clocks/IDs are not emitted.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import dispatch as r44
from direct_camera_r47_20261121 import dispatch as r47


RECEIPT = re.compile(r'TX (\w+) request=(none|0(?:\.\d+)?|1(?:\.0+)?) settled=(\d+)')
SETTLE = re.compile(r'R(47|48)_SETTLE (\d+)')
# R46 page_writes (used by R47): exact opcode writes with tag-local context.
DCS51 = re.compile(r'tx(\d+) page=(\?|[\da-f]{2}@tx\d+) type=(0x[\da-f]+) (lp|hs) (51(?: [\da-f]{2})*)')


def receipts(archive):
    path = archive / 'acquisition.log'
    result = {}
    for line in path.read_text().splitlines() if path.exists() else ():
        if line.split(maxsplit=1)[:1] == ['TX']:
            m = RECEIPT.fullmatch(line)
            if not m or m[1] in result:
                raise ValueError('malformed or duplicate acquisition TX receipt')
            result[m[1]] = m[2], int(m[3])
    return result


def summarize(tag, klog, capture, receipt, refs, dc_refs):
    row = r47.summarize(tag, klog, refs)
    begin = row.pop('begin_s')
    del row['end_s']
    dc = r44.summarize(tag, klog, dc_refs)
    for side in ('on', 'off'):
        row['exact_dc_' + side] = dc['exact_' + side]
        if dc['exact_' + side]:
            spans = [f'tx{a}-{b} DC_{side.upper()}' for a, b in r47.hits(dc, side)]
            row['exact_sets'] = '; '.join(filter(None, [row['exact_sets'], *spans]))

    trace = r47.trace_summary(tag, klog, capture)
    # R47's ordered details include absolute trace times. Retain only entry
    # levels; caller attribution for MOT sends is already counted separately.
    entries = trace.pop('apl_trace_events') or ''
    levels = [int(x) for x in re.findall(r'\bentry level=(\d+)', entries)]
    del trace['send_callers']
    row.update(trace)
    row.update(ctrl_minus_observed_tx=None, request=None, receipt_bl=None, settle_samples=None, settled_bl=None,
               backlight_from_to=None, native_apl_input_levels=None, last_native_apl_input=None,
               last51_page=None, last51_opcode=None, last51_payload=None, last51_operand_be=None,
               operand_sequence_matches_inputs=None, integrity=None, switch_evidence=None,
               settled_evidence='unqualified')
    issues = []
    if receipt:
        row['request'], row['receipt_bl'] = receipt
    if row['bracket'] != 'ok' or row['invalid_tx'] or row['loss_notices']:
        issues.append('incomplete printk interval')
    if row['trace_status'] != 'ok':
        issues.append('incomplete trace')
    if any(row[name + '_profile_missed'] != 0 for name in r47.PROBES):
        issues.append('missing probe profile or missed hits')
    if row['trace_status'] == 'ok' and row['bracket'] == 'ok':
        nctrl = sum(int(pair.split(':')[1]) for pair in row['ctrl_rc_hist'].split())
        # The controller also handles non-write transfers. The printk TX list
        # is not the inventory to which kprobe_profile hits are reconciled.
        row['ctrl_minus_observed_tx'] = nctrl - row['observed_tx']

    # SETTLE lines are printed before the observer copies its KLOG section.
    head = capture[:capture.index('R44_KLOG')] if capture and 'R44_KLOG' in capture else []
    samples = [SETTLE.fullmatch(s) for s in head if s.startswith(('R47_SETTLE', 'R48_SETTLE'))]
    if all(samples):
        row['settle_samples'] = ' '.join(m[2] for m in samples)
    if len(samples) != 3 or not all(samples) or len({m.groups() for m in samples}) != 1:
        issues.append('expected three equal settle reads')
    else:
        row['settled_bl'] = int(samples[0][2])
        if receipt and row['receipt_bl'] != row['settled_bl']:
            issues.append('settle reads differ from receipt')

    candidates = []
    if row['bracket'] == 'ok':
        active = False
        requests = []
        for line in klog:
            mark = r44.MARK.fullmatch(line)
            if mark and mark[2] == tag:
                active = mark[3] == 'BEGIN'
            elif active and (m := re.search(r'\bset_backlight from (\d+) to (\d+)\b', line)):
                requests.append(f'{m[1]}->{m[2]}')
        row['backlight_from_to'] = '; '.join(requests)
        writes = row['dcs51_tx'].split('; ') if row['dcs51_count'] else []
        for write in writes:
            m = DCS51.fullmatch(write)
            if not m:
                raise ValueError(f'{tag}: invalid R46 opcode-51 summary')
            _, page, dtype, _, payload = m.groups()
            data = bytes.fromhex(payload)
            operand = int.from_bytes(data[1:], 'big') if dtype == '0x39' and len(data) == 3 else None
            row.update(last51_page='UNKNOWN' if page == '?' else page, last51_opcode='0x51',
                       last51_payload=payload, last51_operand_be=operand)
            if operand is not None and (page == '?' or page.startswith('00@')):
                candidates.append(operand)
    if row['apl_entries'] is not None:
        if len(levels) != row['apl_entries']:
            raise ValueError(f'{tag}: invalid R47 entry summary')
        row.update(native_apl_input_levels=' '.join(map(str, levels)),
                   last_native_apl_input=levels[-1] if levels else None)
    row['integrity'] = '; '.join(issues) or 'ok'
    if not issues:
        switches = [row['exact_sets'], row['shared_hs_prefixes']]
        if row['oem_apl_count']:
            switches.append('OEM APL config')
        if row['apl_send_returns']:
            switches.append('MOT return from APL')
        if row['send_returns'] > row['apl_send_returns']:
            switches.append('MOT return from other caller')
        row['switch_evidence'] = '; '.join(filter(None, switches)) or 'no identified APL/HBM/DC dispatch'
        if levels or writes:
            row['operand_sequence_matches_inputs'] = int(bool(candidates) and candidates == levels)
            if (row['operand_sequence_matches_inputs'] and len(candidates) == len(writes)
                    and levels[-1] == row['settled_bl']):
                row['settled_evidence'] = '0x51 operand + native input + sysfs agree'
            else:
                row['settled_evidence'] = 'unconfirmed: operands, inputs or sysfs disagree'
        else:
            row['settled_evidence'] = 'sysfs only; no 0x51 or native input'
    return Decimal(begin or 'Infinity'), row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('archive', metavar='ARCHIVE', type=Path)
    archive = parser.parse_args().archive
    try:
        paths = sorted(archive.glob('*.klog'))
        requests = receipts(archive)
        tags = {p.stem for p in paths}
        if not tags or (requests.keys() | {p.stem for p in archive.glob('*.capture')}) - tags:
            raise ValueError('missing TAG.klog for archive, receipt or capture')
        refs, dc_refs = r47.references(), r44.references()
        rows = []
        for p in paths:
            if not re.fullmatch(r'[A-Za-z0-9_]+', p.stem):
                raise ValueError('invalid observer tag')
            capture = p.with_suffix('.capture')
            rows.append(summarize(p.stem, p.read_text().splitlines(),
                                  capture.read_text().splitlines() if capture.exists() else None,
                                  requests.get(p.stem), refs, dc_refs))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0][1], lineterminator='\n')
    writer.writeheader()
    writer.writerows(row for _, row in sorted(rows, key=lambda item: (item[0], item[1]['tag'])))
    return int(any(row['integrity'] != 'ok' for _, row in rows))


if __name__ == '__main__':
    sys.exit(main())
