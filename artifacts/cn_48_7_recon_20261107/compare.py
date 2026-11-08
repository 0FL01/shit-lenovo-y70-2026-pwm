#!/usr/bin/env python3
"""Offline CN48 DTBO versus saved live BOE v4 properties; no device I/O."""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from inspect_cn_dtbo import read_fdt, packets

PANEL = ROOT / 'artifacts/device_tree/selected_boe_v4'
NODE = 'qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4'


def compare(image):
    data = image.read_bytes()
    magic, total, header, entry, count, table, page, version = struct.unpack_from('>8I', data)
    if (magic, header, entry, version) != (0xd7b7ab1e, 32, 32, 0):
        raise ValueError('Unexpected DTBO header')
    if total > len(data) or table+entry*count > total:
        raise ValueError('DTBO table outside image')
    matches = []
    for i in range(count):
        size, offset, *_ = struct.unpack_from('>8I', data, table+i*entry)
        if offset+size > total:
            raise ValueError('DTB outside container')
        nodes = read_fdt(data[offset:offset+size])
        for node, properties in nodes.items():
            if node.endswith('/'+NODE) and 'qcom,mdss-dsi-panel-name' in properties:
                values = {}
                for child, props in nodes.items():
                    if child == node or child.startswith(node+'/'):
                        prefix = child[len(node):].strip('/')
                        for key, (_, value) in props.items():
                            values[(prefix+'/' if prefix else '')+key] = value
                matches.append((i, offset, node, values))
    if len(matches) != 1:
        raise ValueError(f'Expected one panel subtree, found {len(matches)}')
    index, offset, node, reference = matches[0]
    target = {str(p.relative_to(PANEL)): p.read_bytes() for p in PANEL.rglob('*') if p.is_file()}
    differences, commands = [], []
    for key in sorted(reference.keys() | target.keys()):
        a, b = reference.get(key), target.get(key)
        if key.endswith('-command'):
            # This property is a u32 control, not the serialized DSI packet format.
            # dsi_panel.c parses it with read_u32, despite the -command suffix.
            scalar = key == 'qcom,mdss-dsi-te-dcs-command'
            if scalar and any(v is not None and len(v) != 4 for v in (a, b)):
                raise ValueError('Unexpected TE command scalar size')
            commands.append({'property': key, 'equal': a == b,
                             'format': 'u32' if scalar else 'dsi_packets',
                             'reference_packets': len(packets(a)) if a is not None and not scalar else None,
                             'target_packets': len(packets(b)) if b is not None and not scalar else None})
        if a != b:
            differences.append({'property': key,
                                'reference_hex': a.hex(' ') if a is not None else None,
                                'target_hex': b.hex(' ') if b is not None else None})
    return {'scope': 'Offline binary table comparison; no firmware flash compatibility claim',
            'reference_build': 'W3WWL36.65-48-7', 'target_build': 'W3WWS36.65-64-4-1',
            'image': str(image), 'dtbo_entries': count, 'selected_entry': index,
            'dtb_offset': offset, 'selected_node': node,
            'reference_properties': len(reference), 'target_properties': len(target),
            'equal_shared_properties': sum(reference[k] == target[k] for k in reference.keys() & target.keys()),
            'differences': differences, 'commands': commands,
            'equal_command_properties': sum(row['equal'] for row in commands),
            'equal_packet_arrays': sum(row['equal'] and row['format'] == 'dsi_packets' for row in commands),
            'physical_pwm_hz': None, 'device_io': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = compare(args.image)
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('reference_properties', 'target_properties',
                                           'equal_shared_properties', 'equal_command_properties',
                                           'equal_packet_arrays')}))


if __name__ == '__main__':
    main()
