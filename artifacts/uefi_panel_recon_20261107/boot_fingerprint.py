#!/usr/bin/env python3
"""Bounded offline UEFI-write versus archived-read address comparison."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets
from analyze import check, xml_init

CACHE = Path('/home/stfu/.cache/opencode-tmp/opencode/uefi-panel-recon-20261107/global64/display')
PANEL = ROOT / 'artifacts/device_tree/selected_boe_v4'
DUMPS = ROOT / 'artifacts/ddic_regdump_20261107'
PREFIX = 'Panel_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v'


def writes(packets):
    """Last data write per selected page/opcode; FF 5A A5 is a selector, not data."""
    result = {}
    for packet in packets:
        payload = bytes.fromhex(packet['payload'])
        if len(payload) == 4 and payload[:3] == b'\xff\x5a\xa5':
            continue
        if packet['page'] is not None and len(payload) >= 2:
            result[(packet['page'], payload[0])] = payload[1:]
    return result


def analyze():
    names = [CACHE / f'{PREFIX}{v}.xml.raw' for v in range(5)]
    check(all(path.is_file() for path in names), 'Missing pinned GLOBAL64 UEFI XML')
    init = [xml_init(path) for path in names]
    check([len(packets) for packets in init] == [53, 24, 95, 136, 95],
          'Unexpected GLOBAL64 panel command counts')
    variants = [writes(packets) for packets in init]
    paths = [PANEL / 'qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-on-command',
             PANEL / 'qcom,mdss-dsi-dc-off-command',
             PANEL / 'qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-timing-switch-command']
    parsed = [parse_packets(path.read_bytes()) for path in paths]
    check([len(p) for p in parsed] == [95, 75, 14], 'Unexpected selected DT packets')
    check([{'page': p['page'], 'type': bytes.fromhex(p['header'])[0],
            'payload': p['payload'], 'delay_value': bytes.fromhex(p['header'])[4]}
           for p in parsed[0]] == init[4], 'Selected Android v4 init differs from reference v4')
    later = set().union(*(writes(p) for p in parsed))
    keys = set().union(*(set(variant) for variant in variants))
    changed = {key for key in keys if len({v.get(key) for v in variants}) > 1}
    remaining = changed - later

    archived = {}
    for path in sorted(DUMPS.glob('*/registers.json')):
        data = json.loads(path.read_text())
        if len(data) == 4864:
            archived[path.parent.name] = data
    check(set(archived) == {'s1_dbv3584_120', 's2_dbv3646_120',
                            's3_dbv3584_144', 's4_dbv3584_60'}, 'Unexpected full dumps')
    observed = {(int(key[:2], 16), int(key[3:], 16))
                for dump in archived.values() for key in dump
                if len(key) == 5 and key[2] == ':'}
    overlap = sorted(remaining & observed)
    candidates = []
    for page, opcode in overlap:
        address = f'{page:02X}:{opcode:02X}'
        only = [v for v in range(5) if (page, opcode) in variants[v]]
        matches = {v: sum(bytes.fromhex(dump[address]).startswith(variants[v][page, opcode])
                          for dump in archived.values()) for v in only}
        candidates.append({'address': address, 'write_present_in': only,
                           'write_data_bytes': {str(v): len(variants[v][page, opcode]) for v in only},
                           'archived_prefix_matches_out_of_four': {str(v): n for v, n in matches.items()}})
    check(len(changed) == 96 and len(remaining) == 43 and len(overlap) == 18,
          'Unexpected variant/address comparison')
    return {'scope': 'GLOBAL64 reference init v0-v4 and stored selected-v4 command addresses versus four historical long-read dictionaries; no boot execution or response-length qualification',
            'reference_xml': [str(path) for path in names],
            'selected_arrays': [str(path.relative_to(ROOT)) for path in paths],
            'archived_dumps': sorted(archived), 'variant_write_presence_or_value_differences': len(changed),
            'overwritten_if_all_three_selected_arrays_execute': len(changed & later),
            'not_overwritten_in_these_three_arrays': len(remaining),
            'survivors_not_in_archived_pages': len(remaining - observed),
            'survivors_with_archived_addresses': candidates,
            'limits': ['Absence of a UEFI write is not a DDIC default value',
                       'The three selected Android arrays are a conditional address overlay, not a boot trace',
                       'Legacy 40-byte readback does not qualify response length or payload',
                       'No inference of live boot variant, silicon revision, page semantics or OLED PWM Hz'],
            'physical_pwm_hz': None, 'device_io': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    result = analyze()
    with args.output.open('x') as out:
        out.write(json.dumps(result, indent=2) + '\n')
    print('PASS: bounded offline UEFI write / selected DT / archived address comparison')
