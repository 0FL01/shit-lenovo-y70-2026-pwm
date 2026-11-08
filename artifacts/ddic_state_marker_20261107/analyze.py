#!/usr/bin/env python3
"""Find stable brightness-associated first-byte observations in archived DDIC reads."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets

STATES = ('s1_dbv3584_120', 's2_dbv3646_120', 's3_dbv3584_144', 's4_dbv3584_60')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def analyze():
    tables, observations = [], []
    for state in STATES:
        folder = ROOT/'artifacts/ddic_regdump_20261107'/state
        passes = {1: {}, 2: {}}
        for number, line in enumerate((folder/'raw.txt').read_text().splitlines(), 1):
            if not line.startswith('R '):
                continue
            fields = line.split()
            check(len(fields) == 44, 'Unexpected read format')
            pass_no = int(fields[1])
            key = (int(fields[2], 16), int(fields[3], 16))
            check(pass_no in passes and key not in passes[pass_no], 'Pass/duplicate error')
            passes[pass_no][key] = (bytes(int(v, 16) for v in fields[4:]), number)
        check(all(len(p) == 4864 for p in passes.values()), 'Incomplete pass')
        check(passes[1].keys() == passes[2].keys(), 'Mismatching pass keys')
        run = json.loads((folder/'run.json').read_text())
        dbv = [e['stdout'].strip() for e in run['events']
               if e['command'] == "su -c 'cat /sys/class/backlight/panel0-backlight/brightness'"
               and e['exit_code'] == 0]
        expected = '3646' if state == STATES[1] else '3584'
        check(len(dbv) == 2 and dbv == [expected, expected], 'DBV before/after mismatch')
        summary = json.loads((folder/'registers.json').read_text())
        marker = []
        for pass_no, table in passes.items():
            raw, number = table[(7, 0xec)]
            check(raw == bytes.fromhex(summary['07:EC']), 'Marker raw/summary mismatch')
            marker.append({'pass': pass_no, 'raw_line': number, 'first_byte': f'{raw[0]:02x}'})
        observations.append({'state': state, 'requested_refresh': run['refresh_request'],
                             'dbv_before_after': dbv, '07:EC': marker})
        tables.append(passes)
    keys = tables[0][1].keys()
    check(all(p.keys() == keys for t in tables for p in t.values()), 'Different address sets')
    checks = []
    for width in (1, 2, 6, 40):
        stable = [k for k in keys if all(t[1][k][0][:width] == t[2][k][0][:width] for t in tables)]
        selected = [k for k in stable if
                    tables[0][1][k][0][:width] == tables[2][1][k][0][:width] == tables[3][1][k][0][:width]
                    and tables[1][1][k][0][:width] != tables[0][1][k][0][:width]]
        expected_keys = {(7, 0xec)} if width == 1 else {(7, 0xec)} | {k for k in keys if k[1] == 0x52}
        check(set(selected) == expected_keys, 'Marker selection changed')
        checks.append({'prefix_bytes': width, 'stable_across_passes_all_states': len(stable),
                       'selected_addresses': len(selected),
                       'selected_except_brightness_opcode52': ['07:EC']})
    writes, properties = [], 0
    for path in (ROOT/'artifacts/device_tree/selected_boe_v4').rglob('*-command'):
        if path.stat().st_size <= 4:
            continue  # TE scalar, not a packet array.
        properties += 1
        for packet in parse_packets(path.read_bytes()):
            if (packet['page'], packet['opcode']) == (7, 0xec):
                writes.append(str(path.relative_to(ROOT)))
    check(properties == 52 and not writes, 'Unexpected native writer / incomplete scan')
    return {'scope': 'Archived observations only; not a validated register map or causal/optical trial',
            'observations': observations, 'selection_checks': checks,
            'actual_dt_packet_properties_checked': properties, '07:EC_native_writes': writes,
            'physical_pwm_hz': None, 'device_io': False,
            'limits': ['Single high-DBV state; brightness/history/time confounded',
                       'Requested40 bytes are not a proven valid response length',
                       'Only first byte used as candidate state marker; no write semantics',
                       'No simultaneous optical capture in these four dump runs']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print('PASS: archived07:EC2f/10 marker;8passes;before/afterDBV;52nativearrays without07:EC write')
