#!/usr/bin/env python3
"""Find literal EFI DisplayPanelVer consumers in the saved CN48 FV (offline)."""
import json
from pathlib import Path
import re
import subprocess
import sys

FV = Path('/home/stfu/.cache/opencode-tmp/opencode/cn48-bootloader-recon-20261108/uefi.elf.1000.fv')
BOOT = Path('/home/stfu/.cache/opencode-tmp/opencode/cn48-bootloader-recon-20261108/abl.elf.1000.fv')
LIMIT = 2_000_000
NEEDLES = {'utf16le_version': 'DisplayPanelVer'.encode('utf-16le') + b'\0\0',
           'utf16le_secondary': 'DisplayPanelVerSec'.encode('utf-16le') + b'\0\0',
           'ascii_version': b'DisplayPanelVer\0'}


def members(volume):
    out = subprocess.run(['7z', 'l', '-slt', str(volume)], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    entries = []
    for block in out.split('\n\n'):
        fields = dict(m.groups() for line in block.splitlines()
                      if (m := re.fullmatch(r'([^=]+) = (.*)', line)))
        name = fields.get('Path', '')
        if name.endswith('.efi'):
            size = int(fields['Size'])
            if not 0 < size <= LIMIT or not name.startswith(('D14C51ED/', '9E21FD93/')):
                raise ValueError('Unexpected FV member path/size')
            entries.append((name, size))
    if len(entries) != len({name for name, _ in entries}):
        raise ValueError('Repeated FV member')
    return entries


def analyze():
    result = []
    for volume, expected in ((FV, 116), (BOOT, 1)):
        entries = members(volume)
        if len(entries) != expected:
            raise ValueError('Unexpected EFI member count')
        hits = []
        for name, size in entries:
            data = subprocess.run(['7z', 'e', '-so', str(volume), name],
                                  capture_output=True, check=True, timeout=30).stdout
            if len(data) != size or not data.startswith(b'MZ'):
                raise ValueError('Invalid or incomplete PE extraction')
            found = {label: [hex(i) for i in range(len(data)) if data.startswith(needle, i)]
                     for label, needle in NEEDLES.items()}
            found = {k: v for k, v in found.items() if v}
            if found:
                hits.append({'member': name, 'bytes': size, 'literal_offsets': found})
        result.append({'volume': volume.name, 'efi_members_scanned': len(entries),
                       'total_member_bytes': sum(size for _, size in entries), 'hits': hits})
    return {'scope': 'Bounded literal scan of already saved CN48 FV EFI members, not code execution',
            'volumes': result,
            'limit': 'No literal does not exclude computed names, indirect producers or other boot stages',
            'device_io': False, 'physical_pwm_hz': None}


if __name__ == '__main__':
    output = Path(sys.argv[1])
    if output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with output.open('x') as file:
        file.write(json.dumps(result, indent=2) + '\n')
    print('PASS: scoped EFI literal scan; volumes', [(v['volume'], v['efi_members_scanned'],
                                                      len(v['hits'])) for v in result['volumes']])
