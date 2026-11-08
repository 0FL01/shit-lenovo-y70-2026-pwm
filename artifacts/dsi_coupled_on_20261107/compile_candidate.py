#!/usr/bin/env python3
"""Build an unapproved native-value interaction control; never contacts a device."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets


def main():
    out = Path(__file__).resolve().parent
    panel = ROOT / 'artifacts/device_tree/selected_boe_v4'
    stock = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
    native_on = (panel / 'qcom,mdss-dsi-dc-on-command').read_bytes()
    before, after = parse_packets(stock), parse_packets(native_on)
    assert len(stock) == len(native_on) == 875 and len(before) == len(after) == 75
    candidate = bytearray(native_on)
    for index, page, opcode, offset in ((6, 0x23, 0xa9, 68), (9, 0x24, 0x9d, 97)):
        a, b = before[index], after[index]
        assert a['page'] == b['page'] == page and a['opcode'] == b['opcode'] == opcode
        assert a['data'] == '0e' and b['data'] == '8e' and a['offset'] + 8 == offset
        candidate[offset] = 0x0e
    candidate = bytes(candidate)
    parsed = parse_packets(candidate)
    assert [p['header'] for p in parsed] == [p['header'] for p in before]
    assert [i for i, (a, b) in enumerate(zip(native_on, candidate)) if a != b] == [68, 97]
    differences = [{'packet': i, 'page': f"{a['page']:02X}", 'opcode': f"{a['opcode']:02X}",
                    'stock_off': a['data'], 'candidate': b['data']}
                   for i, (a, b) in enumerate(zip(before, parsed)) if a['payload'] != b['payload']]
    assert len(differences) == 32
    assert sum(a != b for a, b in zip(stock, candidate)) == 83
    ranges = [(0,253), (253,500), (500,754), (754,864), (864,875)]
    assert [bytes.fromhex(p['header'])[3] for p in parsed] == [64]*74 + [0]
    assert sum(len(parse_packets(candidate[a:b])) for a, b in ranges) == 75
    report = {'status': 'offline-validated-unapproved', 'device_io': False,
        'scope': 'S0C1 interaction: native full ON except both tested selector high bytes remain native OFF; NOT a decoded frequency multiplier',
        'candidate': 'on_keep_pwm_selectors.bin', 'bytes': len(candidate), 'packets': len(parsed),
        'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
        'stock_off_sha256': hashlib.sha256(stock).hexdigest(),
        'native_on_sha256': hashlib.sha256(native_on).hexdigest(),
        'changes_from_native_on': [{'offset': 68, 'page_opcode': '23:A9', 'from': '8e', 'to': '0e'},
                                   {'offset': 97, 'page_opcode': '24:9D', 'from': '8e', 'to': '0e'}],
        'changes_from_stock_off': differences, 'changed_bytes_from_off': 83,
        'native_chunk_ranges': ranges, 'pwm_hz': 'unknown', 'frequency_multiplier': None,
        'greater_equal_2000_hz_verified': False}
    with (out / report['candidate']).open('xb') as f:
        f.write(candidate)
    with (out / 'validation.json').open('x') as f:
        f.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'changes_from_stock_off'}, indent=2))


if __name__ == '__main__':
    main()
