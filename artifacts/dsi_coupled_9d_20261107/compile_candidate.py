#!/usr/bin/env python3
"""Offline-only A0D1C1 interaction candidate: native ON with only A9 left OFF."""
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
    previous = (ROOT / 'artifacts/dsi_coupled_on_20261107/on_keep_pwm_selectors.bin').read_bytes()
    off, on = parse_packets(stock), parse_packets(native_on)
    assert len(stock) == len(native_on) == len(previous) == 875
    assert len(off) == len(on) == 75
    assert (off[6]['page'], off[6]['opcode'], off[6]['data'], on[6]['data']) == (0x23, 0xa9, '0e', '8e')
    assert off[6]['offset'] + 8 == 68
    candidate = bytearray(native_on)
    candidate[68] = stock[68]
    candidate = bytes(candidate)
    packets = parse_packets(candidate)
    assert [i for i, (a, b) in enumerate(zip(native_on, candidate)) if a != b] == [68]
    assert [i for i, (a, b) in enumerate(zip(previous, candidate)) if a != b] == [97]
    assert packets[6]['data'] == '0e' and packets[9]['data'] == '8e'
    assert [p['header'] for p in packets] == [p['header'] for p in off]
    assert [bytes.fromhex(p['header'])[3] for p in packets] == [64]*74 + [0]
    assert packets[-1]['payload'] == 'ff 5a a5 00'
    ranges = [(0,253), (253,500), (500,754), (754,864), (864,875)]
    assert [len(parse_packets(candidate[a:b])) for a,b in ranges] == [23,19,22,10,1]
    changed = [i for i,(a,b) in enumerate(zip(off,packets)) if a['payload'] != b['payload']]
    assert len(changed) == 33 and sum(a != b for a,b in zip(stock,candidate)) == 84
    prior_paths = [p for p in (ROOT / 'artifacts').glob('dsi*/**/*.bin') if p.stat().st_size == 875]
    assert not any(p.read_bytes() == candidate for p in prior_paths), 'Candidate already exists; preserve prior evidence'
    result = {'status': 'offline-validated-unapproved-unrun', 'device_io': False,
        'hypothesis': '9D may select a different optical regime only with the rest of ON loaded and A9 left OFF; not a decoded frequency setter',
        'candidate': 'on_keep_a9_off.bin', 'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
        'stock_sha256': hashlib.sha256(stock).hexdigest(),
        'native_on_sha256': hashlib.sha256(native_on).hexdigest(),
        'bytes': len(candidate), 'packets': len(packets),
        'selectors': {'23:A9': '0e', '24:9D': '8e'},
        'changed_from_native_on_offsets': [68], 'changed_from_s0c1_offsets': [97],
        'changed_from_stock_packets': changed, 'changed_from_stock_bytes': 84,
        'chunk_ranges': ranges, 'prior_875_byte_candidates_compared': len(prior_paths),
        'pwm_hz': 'unknown', 'frequency_multiplier': None,
        'greater_equal_2000_hz_verified': False}
    with (out / result['candidate']).open('xb') as handle:
        handle.write(candidate)
    with (out / 'validation.json').open('x') as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
