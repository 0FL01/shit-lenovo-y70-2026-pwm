#!/usr/bin/env python3
"""Offline archived-DDIC CRC search and conditional 40-byte reassembly model.

Never imports device runners. The model assumes right-aligned valid long packets,
accurate normalized HW count, zeroed allocation and fixed payload truncated to
MRPS. It does NOT qualify live framing, ECC, DDIC semantics or physical PWM Hz.
"""
import argparse
import binascii
from collections import Counter, defaultdict
import json
from pathlib import Path

from audit_pwm_archive import parse_packets

ROOT = Path(__file__).resolve().parents[1]
STATES = ('s1_dbv3584_120', 's2_dbv3646_120', 's3_dbv3584_144', 's4_dbv3584_60')
CONTROLS = {(0x51, 0xa1), (0x51, 0xa2), (0x52, 0x81), (0x52, 0x82),
            (0x53, 0x95), (0x53, 0xa2), *( (0x63, x) for x in range(0xf1, 0xf5))}
REV8 = bytes(int(f'{x:08b}'[::-1], 2) for x in range(256))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def crc16(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x8408 if value & 1 else 0)
    return value


def prefix_crc_matches(raw):
    matches = []
    for n in range(1, len(raw)-1):
        crc = crc16(raw[:n])
        independent = int(f'{binascii.crc_hqx(raw[:n].translate(REV8), 0xffff):016b}'[::-1], 2)
        check(crc == independent, 'Independent CRC implementations disagree')
        if raw[n:n+2] == crc.to_bytes(2, 'little'):
            matches.append(n)
    return matches


def model_read40(payload):
    """Ideal FIFO model only; neither modeled failure means safe kernel refusal.

    BufferError classifies a helper store beyond requested allocation. None
    classifies final fortify-panic if reached. Actual allocator buckets, KASAN,
    corruption or a live crash are NOT modeled/established.

    Header ECC is deliberately not modeled: parser does not inspect it. No ACK,
    hardware errors, count corruption or changing payload between reads modeled.
    The model sends no commands and does not execute target code.
    """
    check(1 <= len(payload) <= 40, 'Model payload must have 1..40 bytes')
    assembled = bytearray(48)
    for offset, mrps in zip((0, 14, 28, 42), (10, 24, 38, 40)):
        data = payload[:mrps]
        packet = bytes((0x1c, len(data), 0, 0)) + data + crc16(data).to_bytes(2, 'little')
        hw_count = len(packet)
        window = packet[-16:].rjust(16, b'\0')
        skip = offset + 16 - hw_count if hw_count > 16 else 0
        check(skip >= 0, 'Unexpected negative FIFO skip')
        copied = window[skip:] if skip < 16 else b''
        if offset+len(copied) > len(assembled):
            raise BufferError('Modeled helper write exceeds requested allocation')
        assembled[offset:offset+len(copied)] = copied
    header = max(16-hw_count, 0)
    check(assembled[header] == 0x1c, 'Model header dispatch differs')
    if len(assembled)-header-4 < 40:
        return None
    return bytes(assembled[header+4:header+44])


def analyze(root=ROOT):
    check(crc16(b'\0') == 0x0f87 and crc16(b'123456789') == 0x6f91, 'CRC known-answer failure')
    native = {}
    path = root/'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command'
    for p in parse_packets(path.read_bytes()):
        key = p['page'], p['opcode']
        if key in CONTROLS:
            check(key not in native, 'Duplicate native control')
            native[key] = bytes.fromhex(p['data'])
    check(native.keys() == CONTROLS, 'Incomplete native controls')
    records, unique, markers, controls = [], defaultdict(list), [], []
    for state in STATES:
        seen = {1: set(), 2: set()}
        path = root/'artifacts/ddic_regdump_20261107'/state/'raw.txt'
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            if not line.startswith('R '):
                continue
            fields = line.split()
            check(len(fields) == 44, 'Expected 40 saved bytes')
            pass_no, page, reg = int(fields[1]), int(fields[2], 16), int(fields[3], 16)
            key = page, reg
            check(pass_no in seen and key not in seen[pass_no], 'Pass/duplicate error')
            seen[pass_no].add(key)
            raw = bytes(int(x, 16) for x in fields[4:])
            record = {'state': state, 'pass': pass_no, 'key': f'{page:02X}:{reg:02X}', 'raw_line': line_no}
            records.append(record)
            unique[raw].append(record)
            if key in native:
                expected = native[key]
                check(raw.startswith(expected), 'Native control prefix mismatch')
                controls.append(record | {'native_prefix_bytes': len(expected),
                                          'crc_immediately_after_native_prefix': raw[len(expected):len(expected)+2] == crc16(expected).to_bytes(2, 'little')})
        check(all(len(keys) == 4864 for keys in seen.values()) and seen[1] == seen[2], 'Incomplete raw pass')
    hits, distribution, overruns = [], Counter(), set()
    for raw, occurrences in sorted(unique.items()):
        matches = prefix_crc_matches(raw)
        if matches:
            hits.append({'raw': raw.hex(' '), 'prefix_lengths': matches, 'occurrences': occurrences})
        compatible = []
        for n in range(1, 41):
            try:
                reconstructed = model_read40(raw[:n])
            except BufferError:
                overruns.add(n)
                continue
            if reconstructed == raw:
                compatible.append(n)
        distribution[','.join(map(str, compatible))] += 1
        for record in occurrences:
            if record['key'] in ('07:EC', '23:C1'):
                markers.append(record | {'raw': raw.hex(' '), 'crc_prefix_matches': matches,
                                         'conditional_compatible_payload_lengths': compatible})
    check(len(controls) == 80 and len(markers) == 16, 'Incomplete control/marker coverage')
    return {'scope': 'Archived data and conditional ideal FIFO model; not live packet-length qualification',
            'raw_records': len(records), 'distinct_40byte_strings': len(unique),
            'crc_prefix_lengths_tested': [1, 38], 'crc_hits': hits,
            'distinct_strings_by_conditional_lengths': dict(sorted(distribution.items())),
            'markers': sorted(markers, key=lambda r: (r['state'], r['pass'], r['key'])),
            'native_prefix_controls': controls,
            'model': {'requested': 40, 'allocation': 48, 'mrps': [10, 24, 38, 40],
                      'destination_offsets': [0, 14, 28, 42],
                      'payload_lengths_with_modeled_helper_allocation_overrun': sorted(overruns),
                      'assumptions': ['Long DCS responses, accurate normalized HWcount and right-aligned last16FIFObytes',
                                      'Fixed payload, truncated to MRPS; zeroed allocation; no ACK/ECC/error simulation',
                                      'P40 always reproduces input by construction, NOT evidence that live WC=40']},
            'limits': ['CRC coincidences are not qualified packet boundaries',
                       'No raw headers/WC/HWcounts in these archives',
                       'No checksum absence -> payload-length or DDIC-register semantics inference'],
            'device_io': False, 'physical_pwm_hz': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with args.output.open('x') as out:
        out.write(json.dumps(result, indent=2)+'\n')
    print(f"PASS: {result['raw_records']} reads; {result['distinct_40byte_strings']} distinct strings;80native controls; no live qualification")
