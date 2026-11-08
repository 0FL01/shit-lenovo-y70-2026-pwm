#!/usr/bin/env python3
"""Offline structure checks, not a DDIC decoder; never imports device runners."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets

KEYS = ('51:A1', '51:A2', '52:81', '52:82', '53:95', '53:A2',
        '63:F1', '63:F2', '63:F3', '63:F4')
GROUPS = ((0x51, 0x80), (0x51, 0xa0), (0x51, 0xc0), (0x52, 0x80), (0x52, 0xa0))
STATES = ('s1_dbv3584_120', 's2_dbv3646_120', 's3_dbv3584_144', 's4_dbv3584_60')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def target_payloads(state):
    path = ROOT / 'artifacts/device_tree/selected_boe_v4' / f'qcom,mdss-dsi-dc-{state}-command'
    found = {}
    for packet in parse_packets(path.read_bytes()):
        key = f'{packet["page"]:02X}:{packet["opcode"]:02X}'
        if key in KEYS:
            check(key not in found, f'Duplicate scoped write {key}')
            found[key] = bytes.fromhex(packet['data'])
    check(set(found) == set(KEYS), 'Incomplete scoped native program')
    return found


def analyze():
    off, on = target_payloads('off'), target_payloads('on')
    evidence = []
    for state in STATES:
        folder = ROOT / 'artifacts/ddic_regdump_20261107' / state
        reads = {1: {}, 2: {}}
        for number, line in enumerate((folder / 'raw.txt').read_text().splitlines(), 1):
            if not line.startswith('R '):
                continue
            fields = line.split()
            check(len(fields) == 44, f'Unexpected read length at {state}:{number}')
            pass_no = int(fields[1])
            check(pass_no in reads, 'Unexpected pass')
            key = f'{int(fields[2], 16):02X}:{int(fields[3], 16):02X}'
            check(key not in reads[pass_no], 'Duplicate read in pass')
            reads[pass_no][key] = (bytes(int(v, 16) for v in fields[4:]), number)
        saved = json.loads((folder / 'registers.json').read_text())
        passes = []
        for pass_no, table in reads.items():
            check(len(table) == 4864, 'Incomplete archived pass')
            prefixes = []
            for key, expected in off.items():
                actual, line = table[key]
                check(actual[:len(expected)] == expected, f'Native prefix mismatch {state}:{key}')
                check(actual == bytes.fromhex(saved[key]), 'Summary differs from raw scoped read')
                prefixes.append({'key': key, 'raw_line': line, 'prefix_bytes': len(expected)})
            for page, base in GROUPS:
                groups = [b''.join(table[f'{page:02X}:{op:02X}'][0][:6]
                                  for op in range(base+8*i, base+8*i+8)) for i in range(4)]
                check(len(set(groups)) == 1, 'Repeated-window observation changed')
            passes.append({'pass': pass_no, 'scoped_prefix_matches': prefixes,
                           'five_quartets_of_eight_opcode_windows_equal': True})
        evidence.append({'state': state, 'passes': passes})
    # A conditional representation only: two plausible nibble orders both fit.
    models = []
    for key in KEYS[:4]:
        values = {}
        for state, payload in (('off', off[key]), ('on', on[key])):
            check(len(payload) == 6, 'Not a six-byte payload')
            candidates = [[payload[i] | (((payload[4+i//2] >> shift(i)) & 15) << 8)
                           for i in range(4)]
                          for shift in (lambda i: 4*(i % 2), lambda i: 4*(1-i % 2))]
            check(candidates[0] == candidates[1], 'Nibble orders distinguishable here')
            values[state] = candidates[0]
        models.append({'key': key, 'conditional_4x12bit_values': values,
                       'nibble_order_identifiable': False, 'gamma_or_timing_semantics': 'unknown'})
    return {'scope': 'Existing target writes and raw archived read prefixes only; no device I/O',
            'native_payloads': {s: {k: v.hex(' ') for k, v in p.items()}
                                for s, p in (('off', off), ('on', on))},
            'archived_evidence': evidence,
            'repeated_windows': [{'page': f'{p:02X}', 'starts': [f'{b+8*i:02X}' for i in range(4)]}
                                 for p, b in GROUPS],
            'conditional_models': models,
            'limits': ['Requested forty bytes do not establish valid response length',
                       'Repeated windows do not distinguish aliases from duplicated banks',
                       'No address auto-increment or write alias is inferred',
                       'Neither gamma packing nor a sequencer instruction set is established'],
            'physical_pwm_hz': None, 'new_dsi_sent': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print('PASS: 8 archived passes, 80 native-prefix matches, 40 repeated-window checks; Hz unknown')
