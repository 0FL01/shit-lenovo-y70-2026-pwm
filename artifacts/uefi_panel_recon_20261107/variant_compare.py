#!/usr/bin/env python3
"""Compare BOE ILI97701A UEFI variants with pinned public DT source; offline only."""
import argparse
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets
from analyze import check, xml_init

PIN = 'kernel-display-devicetree-f088523dfba85c95c15f43726fcf972c0c7a957a'
STEM = 'dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common'
XML = 'Panel_mot_boe_ili97701A_682_1440x3168_dsc_cmd'


def source_timing_zero(tar, variant):
    name = f'{PIN}/display/{STEM}_v{variant}.dtsi'
    member = tar.getmember(name)
    check(member.isfile(), f'Not a regular DT source: {name}')
    source = tar.extractfile(member).read().decode('utf-8')
    matches = re.findall(r'qcom,mdss-dsi-on-command\s*=\s*\[(.*?)\];', source, re.S)
    check(len(matches) == 8, f'Unexpected timing count in v{variant}')
    text = re.sub(r'//[^\n]*|/\*.*?\*/', '', matches[0], flags=re.S)
    tokens = text.split()
    check(tokens and all(re.fullmatch(r'[0-9a-fA-F]{2}', s) for s in tokens),
          'Non-byte token in DT property')
    return format_packets(parse_packets(bytes.fromhex(''.join(tokens))))


def format_packets(packets):
    return [{'page': p['page'], 'type': bytes.fromhex(p['header'])[0],
             'payload': p['payload'], 'delay_value': bytes.fromhex(p['header'])[4]}
            for p in packets]


def analyze(archive, cache):
    variants = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for v in (2, 3, 4):
            dt = source_timing_zero(tar, v)
            cn = xml_init(cache / 'cn11/display' / f'{XML}_v{v}.xml.raw')
            gl = xml_init(cache / 'global64/display' / f'{XML}_v{v}.xml.raw')
            check(dt == cn, f'CN bootloader v{v} differs from pinned DT timing@0')
            variants[v] = gl
    a, b, c = (variants[v] for v in (2, 3, 4))
    delta_2_4 = [i for i, (x, y) in enumerate(zip(a, c)) if x != y]
    delta_3_prefix = [i for i, (x, y) in enumerate(zip(b[:94], c[:94])) if x != y]
    check(len(a) == len(c) == 95 and len(b) == 136, 'Unexpected GLOBAL packet count')
    check(delta_2_4 == delta_3_prefix == [44, 45, 46], 'Unexpected shared-prefix difference')
    check(b[94:-1] and len(b[94:-1]) == 41 and b[-1] == c[-1],
          'Expected v3-only insertion before final display-on')
    check(all(x['page'] == 0x1e and x['payload'].split()[0] in ('ca', 'cb', 'cc')
              for x in (a[i] for i in delta_2_4)), 'Unexpected v2/v4 changed opcodes')
    insertion = b[94:-1]
    head = ['ff 5a a5 53', 'f0 01', 'ff 5a a5 63',
            *[f'{x:02x} ' for x in (0xf1, 0xf2, 0xf3, 0xf4, 0xf8, 0xf9, 0xfa)],
            'ff 5a a5 53', 'f0 00', 'ff 5a a5 2f', '99 e4']
    check(all(x['payload'].startswith(prefix) and x['page'] == page
              for x, prefix, page in zip(insertion[:14], head,
                                         [0x53, 0x53, *([0x63] * 8), 0x53, 0x53, 0x2f, 0x2f])),
          'Unexpected v3 bootstrap sequence')
    check([(x['page'], x['payload']) for x in insertion[-3:]] ==
          [(0x2f, 'ff 5a a5 2f'), (0x2f, '99 00'), (0, 'ff 5a a5 00')],
          'Unexpected v3 insertion trailer')
    p2f = [x for x in insertion if x['page'] == 0x2f and
           0x80 <= int(x['payload'].split()[0], 16) <= 0x97]
    check(len(p2f) == 24 and all(len(bytes.fromhex(x['payload'])) == 7 for x in p2f),
          'Unexpected v3-only 2F table geometry')
    check(p2f == insertion[14:38] and
          [x['payload'].split()[0] for x in p2f] == [f'{x:02x}' for x in range(0x80, 0x98)],
          'Unexpected v3 2F table order')
    off = parse_packets((ROOT / 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command').read_bytes())
    matching = []
    for opcode in range(0xf1, 0xf5):
        key = f'{opcode:02x} '
        from_v3 = [x['payload'] for x in insertion if x['page'] == 0x63 and x['payload'].startswith(key)]
        from_off = [x['payload'] for x in off if x['page'] == 0x63 and x['opcode'] == opcode]
        check(len(from_v3) == len(from_off) == 1 and from_v3 == from_off,
              f'v3 bootstrap 63:{opcode:02X} != selected v4 native DC OFF')
        matching.append(f'63:{opcode:02X}')
    selected = format_packets(parse_packets((ROOT / 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-on-command').read_bytes()))
    check(c == selected, 'Selected v4 init differs from GLOBAL UEFI v4')
    return {'scope': 'Offline CN11/GLOBAL64 bootloader XML, pinned public DT, saved selected v4 DT; no live bootloader identity',
            'source_archive': str(archive), 'source_pin': PIN.split('-')[-1],
            'xml_directory': str(cache), 'cn_equals_public_dt_timing0': {'v2': len(a) - 3, 'v3': len(b) - 3, 'v4': len(c) - 3},
            'global_packet_counts': {'v2': len(a), 'v3': len(b), 'v4': len(c)},
            'v2_to_v4_changed_packet_indices_only': delta_2_4,
            'v2_to_v4_changed_page_opcodes': ['1E:CA', '1E:CB', '1E:CC'],
            'v3_to_v4_shared_prefix_changed_indices_only': delta_3_prefix,
            'v3_only_inserted_before_display_on': len(insertion),
            'v3_only_page_2f_table_rows_of_three_pairs': len(p2f),
            'v3_63_f1_f4_equal_selected_v4_dc_off': matching,
            'selected_v4_global_uefi_equals_target_timing0': True,
            'semantic_limit': '2F table and 53:F0/63:F1-F4 emission/PWM semantics unknown; other selected variants not portable',
            'physical_pwm_hz': None, 'device_io': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('cache', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze(args.archive, args.cache)
    with args.output.open('x') as out:
        out.write(json.dumps(result, indent=2) + '\n')
    print('PASS: CN v2/v3/v4 UEFI == public DT; v3-only tail 41, v2→v4 changes three 1E packets')
