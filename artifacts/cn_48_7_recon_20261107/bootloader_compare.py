#!/usr/bin/env python3
"""Bounded offline comparison of the saved CN48 BOE bootloader reference."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'uefi_panel_recon_20261107'))
from analyze import codeview_path, xml_init

ROOT = Path(__file__).resolve().parents[2]
BASE = Path('/home/stfu/.cache/opencode-tmp/opencode')
NEW = BASE / 'cn48-bootloader-recon-20261108'
OLD = BASE / 'uefi-panel-recon-20261107'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def container(data):
    check(data[:16] == b'SINGLE_N_LONELY\0', 'Wrong container header')
    pos, entries = 0x100, {}
    while pos < len(data):
        check(pos + 256 <= len(data), 'Truncated member header')
        raw = data[pos:pos+248]
        name = raw.split(b'\0', 1)[0].decode('ascii')
        check(name and name not in entries and raw[len(name):].strip(b'\0') == b'',
              'Invalid or repeated member name')
        size = struct.unpack_from('<Q', data, pos+248)[0]
        start = pos+256
        end = start+size
        next_pos = start+(size+4095)//4096*4096
        check(end <= next_pos <= len(data) and not any(data[end:next_pos]),
              'Bad member bounds or nonzero padding')
        entries[name] = data[start:end]
        pos = next_pos
        if name == 'LONELY_N_SINGLE':
            check(size == 0 and pos == len(data), 'Bad terminal marker')
            break
    check(len(entries) == 36 and list(entries)[-1] == 'LONELY_N_SINGLE',
          'Unexpected container entries')
    names = [e.attrib['filename'] for e in ET.fromstring(entries['default.xml']).iter('flash')]
    check(len(names) == 32 and set(names) ==
          set(entries) - {'index.xml', 'pkg.xml', 'default.xml', 'LONELY_N_SINGLE'},
          'Partition manifest differs from contained members')
    return entries


def verified_fv(elf, expected_size):
    check(elf[:4] == b'\x7fELF' and len(elf) >= 0x1000+expected_size,
          'Truncated FV-bearing ELF')
    fv = elf[0x1000:0x1000+expected_size]
    check(fv[0x28:0x2c] == b'_FVH' and
          struct.unpack_from('<Q', fv, 0x20)[0] == expected_size,
          'Unexpected FV header/size')
    return fv


def extract_member(volume, prefix, name):
    p = subprocess.run(['7z', 'e', '-so', str(volume), prefix+name],
                       capture_output=True, check=True, timeout=40)
    check(p.stdout and len(p.stdout) <= 2_000_000, 'Missing/oversized FV member')
    return p.stdout


def analyze():
    image = (NEW / 'bootloader.img').read_bytes()
    check(len(image) == 83563776, 'Unexpected CN48 bootloader size')
    entries = container(image)
    for name, size in (('uefi', 0x400000), ('abl', 0x90000)):
        fv = verified_fv(entries[name+'.elf'], size)
        check(fv == (NEW / (name+'.elf.1000.fv')).read_bytes(),
              'FV extraction does not match container')
    names = sorted(p.name for p in (OLD / 'global64/display').glob('Panel_mot_boe_ili97*.xml.raw'))
    check(len(names) == 9, 'Reference panel set incomplete')
    members = {}
    for name in names+['DisplayDxe.efi', 'BacklightDxe.efi']:
        data = extract_member(NEW/'uefi.elf.1000.fv',
                              'D14C51ED/EE4E5898/VOLUME/', name)
        check(data == (NEW/'display'/name).read_bytes(), 'Saved member changed')
        members[name] = data
    boot = extract_member(NEW/'abl.elf.1000.fv',
                          '9E21FD93/EE4E5898/VOLUME/', 'MotoBootModule.efi')
    check(boot == (NEW/'boot/MotoBootModule.efi').read_bytes(), 'Saved boot module changed')
    panels = []
    for name in names:
        data = members[name]
        old = (OLD/'global64/display'/name).read_bytes()
        old_cn = (OLD/'cn11/display'/name).read_bytes()
        check(data == old, 'New CN BOE program differs from GLOBAL64')
        panels.append({'name': name, 'bytes': len(data), 'packets': len(xml_init(NEW/'display'/name)),
                       'cn48_equals_global64': True, 'cn48_equals_cn11': data == old_cn})
    displays = []
    for name in ('DisplayDxe.efi', 'BacklightDxe.efi'):
        data = members[name]
        old = (OLD/'global64/display'/name).read_bytes()
        start, end, path = codeview_path(data)
        ostart, oend, opath = codeview_path(old)
        check(len(data) == len(old) and (start, end) == (ostart, oend) and
              data[:start] == old[:ostart] and data[end:] == old[oend:] and
              path != opath, 'Display PE changed beyond CodeView path')
        displays.append({'name': name, 'bytes': len(data),
                         'different_bytes_in_codeview_only': sum(a != b for a,b in zip(data,old))})
    old_boot = (OLD/'global64/boot/MotoBootModule.efi').read_bytes()
    check(len(boot) == len(old_boot), 'BootModule PE layout differs')
    return {'scope': 'Offline CN48 reference; not target bootloader or physical panel readback',
            'source_image_sha256': hashlib.sha256(image).hexdigest(),
            'container_entries': len(entries), 'manifest_flash_members': 32,
            'uefi_fv_bytes': 0x400000, 'abl_fv_bytes': 0x90000,
            'panels': panels, 'display_modules': displays,
            'boot_module': {'bytes': len(boot),
                            'cn48_equals_global64': boot == old_boot,
                            'cn48_sha256': hashlib.sha256(boot).hexdigest()},
            'device_io': False, 'physical_pwm_hz': None}


if __name__ == '__main__':
    output = Path(sys.argv[1])
    if output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with output.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print('PASS: CN48 bootloader manifest/FV, 9 BOE XML and 2 display PEs compared')
