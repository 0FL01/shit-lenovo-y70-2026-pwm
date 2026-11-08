#!/usr/bin/env python3
"""Decode the bounded BOE version-name catalog in a saved reference DisplayDxe."""
import argparse
import csv
import json
from pathlib import Path
import struct

from analyze import check, codeview_path

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x4e338  # PE import RVA from FUN_0000cb00; not a live address
FAMILY = 'boe_ili97701A_682_1440x3168_dsc_cmd_v'


def pe_offset(data, rva):
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    check(data[pe:pe + 4] == b'PE\0\0', 'Missing PE signature')
    machine, sections, _, _, _, opt_size, _ = struct.unpack_from('<HHIIIHH', data, pe + 4)
    check(machine == 0xaa64 and struct.unpack_from('<H', data, pe + 24)[0] == 0x20b,
          'Not ARM64 PE32+')
    start = pe + 24 + opt_size
    candidates = []
    for i in range(sections):
        _, va, size, raw = struct.unpack_from('<IIII', data, start + 40 * i + 8)
        if va <= rva < va + size and raw + rva - va < len(data):
            candidates.append(raw + rva - va)
    check(len(candidates) == 1, 'Ambiguous/unmapped PE catalog RVA')
    return candidates[0]


def name(data, pos, size=64):
    payload = data[pos:pos + size]
    check(len(payload) == size and b'\0' in payload, 'Invalid catalog name')
    return payload.split(b'\0', 1)[0].decode('ascii')


def analyze(cache):
    files = [(cache / region / 'display/DisplayDxe.efi').read_bytes()
             for region in ('cn11', 'global64')]
    cn, gl = files
    sa, ea, _ = codeview_path(cn)
    sb, eb, _ = codeview_path(gl)
    check((sa, ea) == (sb, eb) and cn[:sa] == gl[:sb] and cn[ea:] == gl[eb:],
          'Regional code/data differ beyond NB10 debug path')
    base = pe_offset(gl, BASE)
    group = [name(gl, base + i * 0x928) for i in range(6)]
    check(group[0] == FAMILY + '1' and group[3] == FAMILY + '0',
          'Unexpected BOE catalog group indices')
    check(gl[base + 0x40:base + 0x4c].hex(' ') ==
          '06 00 00 00 05 00 00 00 da 00 d2 00', 'Changed BOE ID config bytes')
    check(gl[base + 0x78:base + 0x84].hex(' ') ==
          '04 00 00 00 01 00 00 00 dc 00 00 00', 'Changed BOE version config bytes')
    entries = []
    for i in range(32):
        pos = base + 0xa8 + i * 0x44
        check(pos + 0x44 <= len(gl), 'Catalog entry outside PE')
        threshold = struct.unpack_from('<I', gl, pos)[0]
        label = name(gl, pos + 4)
        if label or threshold:
            entries.append({'index': i, 'less_than': threshold, 'profile': label})
    check(entries == [{'index': i, 'less_than': n, 'profile': FAMILY + str(i + 1)}
                      for i, n in enumerate((1, 2, 3, 255))],
          'Unexpected BOE threshold/name catalog')
    rows = list(csv.reader((cache / 'global64/display/PanelSimConfig.csv.raw').read_text().splitlines()))
    check(len(rows) == 46 and not any('boe' in cell.lower() or 'ili97701a' in cell.lower()
                                      for row in rows for cell in row),
          'PanelSimConfig unexpectedly contains a BOE map')
    check((cache / 'cn11/display/PanelSimConfig.csv.raw').read_bytes() ==
          (cache / 'global64/display/PanelSimConfig.csv.raw').read_bytes(),
          'Regional PanelSimConfig mismatch')
    android = json.loads((ROOT / 'artifacts/panel_live_20261106.json').read_text())['panel_attributes']
    check(android['panelName']['value'] == FAMILY + '4' and
          int(android['panelId']['value'], 16) == 0xd2 and
          int(android['panelVer']['value'], 16) == 0,
          'Live Android profile fields changed')
    return {'scope': 'Static reference PE catalog and archived Android software fields, no current UEFI readback',
            'reference_pe_code_data_region_equal_except_nb10': True,
            'reference_pe_import_rva': hex(BASE), 'reference_pe_catalog_file_offset': hex(base),
            'boe_group_index': 0, 'boe_id_config_bytes': gl[base + 0x40:base + 0x4c].hex(' '),
            'boe_version_config_bytes': gl[base + 0x78:base + 0x84].hex(' '),
            'boe_version_less_than_entries': entries,
            'conditional_mapping_if_group0_and_matching_readback':
                {'0': FAMILY + '1', '1': FAMILY + '2', '2': FAMILY + '3',
                 '3..254': FAMILY + '4', '255': 'no threshold match (fallback unknown)'},
            'panelsimconfig_rows_including_header': len(rows), 'panelsimconfig_boe_rows': 0,
            'archived_android_selected_profile': android['panelName']['value'],
            'archived_android_panel_id': android['panelId']['value'],
            'archived_android_panel_ver': android['panelVer']['value'],
            'limits': ['Android panelVer=0 is not established as the UEFI DC readback byte',
                       'Current target UEFI binary/selection trace not captured',
                       'PE reference v3 commands cannot be applied to selected Android v4'],
            'physical_pwm_hz': None, 'device_io': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cache', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze(args.cache)
    with args.output.open('x') as out:
        out.write(json.dumps(result, indent=2) + '\n')
    print('PASS: reference BOE group0 threshold map 1/2/3/255; live boot selection unknown')
