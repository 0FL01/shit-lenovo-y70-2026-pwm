#!/usr/bin/env python3
"""Identify long init payloads against saved PPS/source; no device or network I/O."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets

CACHE = Path('/home/stfu/.cache/opencode-tmp/opencode')
SOURCE = CACHE / 'ddic-4f-followup-20261107/origin-v4-at-f088.dtsi'
LOG = CACHE / 'stock-base-rates-20261107/phase-4-kernel.txt'


def page_payloads(packets, page):
    return [p['payload'] for p in packets if p['page'] == page and not p['is_page_selector']]


def transition_tail(packets):
    start = next(i for i, p in enumerate(packets) if (p['page'], p['opcode']) == (0x2d, 0x97))
    return [p['payload'] for p in packets[start:] if p['page'] == 0x2d and not p['is_page_selector']]


def analyze():
    rows = re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) lp cmds= ([0-9a-fA-F ]+)', LOG.read_text())
    pps_set = {bytes.fromhex(data) for length, kind, data in rows if int(length) == 128 and int(kind, 16) == 0x0a}
    assert len(pps_set) == 1
    pps = pps_set.pop()
    assert len(pps) == 128
    source = SOURCE.read_text()
    array = re.search(r'qcom,mdss-dsi-on-command\s*=\s*\[([^\]]+)\]', source)[1]
    array = re.sub(r'//[^\n]*|/\*.*?\*/', '', array, flags=re.S)
    reference = parse_packets(bytes.fromhex(array))
    modes = []
    base = ROOT / 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings'
    paths = sorted(base.glob('timing@*/qcom,mdss-dsi-on-command'))
    assert len(paths) == 8
    for path in paths:
        packets = parse_packets(path.read_bytes())
        chain = packets[3:13]
        assert [p['opcode'] for p in chain] == [0x81] + [0xfe]*9
        assert all(p['page'] == 7 for p in chain)
        assert [p['payload'] for p in chain] == [p['payload'] for p in reference[3:13]]
        data = b''.join(bytes.fromhex(p['data']) for p in chain)
        assert len(data) == 99 and data[:5] == bytes(5)
        assert data[5:] == pps[:94] and pps[94:] == bytes(34)
        lhbm = page_payloads(packets, 0x1e)
        tail = transition_tail(packets)
        assert lhbm == page_payloads(reference, 0x1e) and len(lhbm) == 10
        assert tail == transition_tail(reference) and len(tail) == 9
        modes.append({'timing': path.parent.name, 'init_packets': len(packets),
                      'dsc_chain_matches_native_pps': True,
                      'lhbm_payloads_equal_pinned_source': True,
                      'transition_tail_equal_pinned_source': True})
    return {
        'status': 'reported; offline byte comparison of saved target evidence',
        'device_io': False, 'source_pin': 'f088523dfba85c95c15f43726fcf972c0c7a957a',
        'source': str(SOURCE), 'captured_pps_source': str(LOG), 'modes': modes,
        'dsc': {'page': '07', 'initial_opcode': '81', 'continuation_opcode': 'FE',
                'prefix_zero_bytes': 5, 'pps_prefix_bytes': 94, 'unwritten_zero_pps_tail_bytes': 34,
                'version_byte': pps[0], 'picture_height': int.from_bytes(pps[6:8], 'big'),
                'picture_width': int.from_bytes(pps[8:10], 'big'),
                'slice_height': int.from_bytes(pps[10:12], 'big'),
                'slice_width': int.from_bytes(pps[12:14], 'big')},
        'source_annotated_lhbm_page_1e_payloads': page_payloads(reference, 0x1e),
        'source_annotated_transition_and_dimming_tail': transition_tail(reference),
        'pwm_hz': 'unknown', 'frequency_multiplier': None,
        'limits': ['Block equality does not establish whole-source or whole-module equivalence.',
                   'Source labels constrain roles, not every bit or indirect optical effect.',
                   'No emission microcode or pulse count/period encoding identified in these blocks.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze()
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'modes_verified': len(result['modes']), 'dsc': result['dsc'], 'device_io': False}))
