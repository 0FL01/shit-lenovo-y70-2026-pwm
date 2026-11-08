#!/usr/bin/env python3
"""Compare extracted reference UEFI display files with saved target DT; no device I/O."""
import argparse
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets


def check(condition, message):
    if not condition:
        raise ValueError(message)


def xml_init(path):
    # Qualcomm panel XML has multiple top-level elements; wrap, do not repair data.
    text = path.read_text()
    check(text.startswith('<?xml ') and '?>' in text, 'Missing XML declaration')
    root = ET.fromstring('<root>' + text.split('?>', 1)[1] + '</root>')
    sequences = root.findall('DSIInitSequence')
    check(len(sequences) == 1, 'Ambiguous init sequence')
    packets, page = [], 0
    for line in sequences[0].text.splitlines():
        if not line.strip():
            continue
        raw = bytes.fromhex(line)
        if raw[0] == 0xff:
            check(len(raw) == 2 and packets, 'Unexpected delay record')
            packets[-1]['delay_value'] += raw[1]
            continue
        check(raw[0] in (0x05, 0x15, 0x39) and len(raw) >= 2, 'Unknown record')
        payload = raw[1:]
        if payload[:3] == bytes.fromhex('ff 5a a5'):
            check(len(payload) == 4, 'Invalid page record')
            page = payload[3]
        packets.append({'page': page, 'type': raw[0], 'payload': payload.hex(' '),
                        'delay_value': 0})
    return packets


def codeview_path(data):
    pe = struct.unpack_from('<I', data, 60)[0]
    check(data[pe:pe+4] == b'PE\0\0', 'Not PE')
    machine, count, _, _, _, opt_size, _ = struct.unpack_from('<HHIIIHH', data, pe+4)
    opt = pe+24
    check(machine == 0xaa64 and struct.unpack_from('<H', data, opt)[0] == 0x20b,
          'Not ARM64 PE32+')
    sections = [struct.unpack_from('<IIII', data, opt+opt_size+40*i+8)
                for i in range(count)]

    def file_offset(rva):
        matches = [ptr+rva-va for vs, va, size, ptr in sections if va <= rva < va+size]
        check(len(matches) == 1, 'Unmapped/ambiguous RVA')
        return matches[0]

    rva, size = struct.unpack_from('<II', data, opt+112+6*8)
    check(size == 28, 'Unexpected debug directories')
    _, _, _, _, kind, length, addr, ptr = struct.unpack_from('<IIHHIIII', data, file_offset(rva))
    check(kind == 2 and file_offset(addr) == ptr and ptr+length <= len(data), 'Bad CodeView')
    check(data[ptr:ptr+4] == b'NB10' and data[ptr+length-1] == 0, 'Unexpected CodeView format')
    start, end = ptr+16, ptr+length-1
    path = data[start:end].decode('ascii')
    check('/tmp_ws_bld_dirs/' in path and path.endswith('.dll'), 'Unexpected debug path')
    return start, end, path


def analyze(cache):
    cn, gl = (cache / label / 'display' for label in ('cn11', 'global64'))
    names = sorted(p.name for p in cn.glob('Panel_mot_boe_ili97*.xml.raw'))
    check(len(names) == 9 and names == sorted(p.name for p in gl.glob('Panel_mot_boe_ili97*.xml.raw')),
          'Incomplete scoped panels')
    panels = [{'name': n, 'cn_bytes': (cn/n).stat().st_size,
               'global_bytes': (gl/n).stat().st_size,
               'byte_equal': (cn/n).read_bytes() == (gl/n).read_bytes()} for n in names]
    target = ROOT / 'artifacts/device_tree/selected_boe_v4'
    filename = 'Panel_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4.xml.raw'
    commands = xml_init(gl/filename)
    init = target/'qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-on-command'
    dt = [{'page': p['page'], 'type': bytes.fromhex(p['header'])[0],
           'payload': p['payload'], 'delay_value': bytes.fromhex(p['header'])[4]}
          for p in parse_packets(init.read_bytes())]
    check(len(commands) == 95 and commands == dt, 'UEFI v4 differs from target timing0')
    binaries = []
    for name in ('DisplayDxe.efi', 'BacklightDxe.efi'):
        a, b = (cn/name).read_bytes(), (gl/name).read_bytes()
        sa, ea, pa = codeview_path(a)
        sb, eb, pb = codeview_path(b)
        check(len(a) == len(b) and (sa, ea) == (sb, eb), 'PE layout changed')
        check(a[:sa] == b[:sb] and a[ea:] == b[eb:], 'Differences outside debug path')
        # Only the Jenkins workspace component may differ, not arbitrary debug content.
        before_a, tail_a = pa.split('/tmp_ws_bld_dirs/', 1)
        before_b, tail_b = pb.split('/tmp_ws_bld_dirs/', 1)
        job_a, after_a = tail_a.split('/', 1)
        job_b, after_b = tail_b.split('/', 1)
        check(before_a == before_b and after_a == after_b, 'Debug path changed elsewhere')
        binaries.append({'name': name, 'bytes': len(a), 'differing_bytes': sum(x != y for x,y in zip(a,b)),
                         'codeview_path_span': [hex(sa), hex(ea)],
                         'cn_workspace': job_a, 'global_workspace': job_b,
                         'everything_except_codeview_workspace_equal': True})
    return {'scope': 'Offline reference CN11/GLOBAL64, not target bootloader identity or execution',
            'panels': panels, 'v4_global_init': commands,
            'target_timing0_packet_type_order_payload_and_numeric_delays_equal': True,
            'delay_limit': 'XML FF-byte values compared with DT wait fields; no runtime timing proof',
            'display_binaries': binaries, 'physical_pwm_hz': None, 'device_io': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze(args.cache)
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print('PASS: 9 panel XMLs; 95 v4 packets equal target timing0; 2 PEs differ only in CodeView workspace')
