#!/usr/bin/env python3
"""Offline evidence extraction from the saved target module; never contacts ADB.

Requires binutils including aarch64-linux-gnu-objdump. Creates a new output
directory, leaving historical outputs untouched. Addresses are ELF section
offsets, NOT runtime addresses. Interpret branches in disassembly, not names.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'artifacts/kernel/gki_r59/target_vendor/msm_drm.ko'
PANEL = ROOT / 'artifacts/device_tree/selected_boe_v4'
FUNCTIONS = (
    'dsi_panel_parse_bl_config', 'dsi_panel_bl_register',
    'dsi_display_set_backlight', 'sde_dimming_bl_notify',
    'dsi_panel_set_backlight', 'dsi_panel_set_apl', 'dsi_panel_set_odc',
    'dsi_panel_set_param', 'dsi_panel_send_param_cmd',
    'dsi_panel_mot_parse_param_commands',
    'dsi_panel_parse_esync_params',
    '_sde_connector_update_dimming_ctrl',
    '_sde_connector_update_dimming_bl_lut',
    '_sde_connector_update_dimming_min_bl',
)


def command(*args):
    return subprocess.check_output(args, text=True, timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New evidence directory; must not exist')
    args = parser.parse_args()
    binary = MODULE.read_bytes()
    sections = command('readelf', '-SW', str(MODULE))
    ro = re.search(r'\]\s+\.rodata\s+PROGBITS\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)', sections)
    if not ro:
        raise ValueError('Missing .rodata section')
    offset, size = (int(x, 16) for x in ro.groups())
    rodata = binary[offset:offset + size]
    symbols = command('nm', '-S', '--defined-only', str(MODULE))
    functions = []
    for line in symbols.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[2] in ('t', 'T'):
            functions.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    names = {name for _, _, name in functions}
    missing = set(FUNCTIONS) - names
    if missing:
        raise ValueError(f'Missing functions: {sorted(missing)}')
    relocations = command('aarch64-linux-gnu-objdump', '-r', '-j', '.text', str(MODULE))
    pwm_calls = []
    for line in relocations.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[2] not in ('pwm_apply_might_sleep', 'devm_pwm_get'):
            continue
        address = int(parts[0], 16)
        owner = [name for start, length, name in functions if start <= address < start + length]
        if len(owner) != 1:
            raise ValueError(f'Ambiguous owner for PWM relocation: {line}')
        pwm_calls.append({'text_offset': hex(address), 'callee': parts[2], 'owner': owner[0]})

    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'text-relocations.txt').write_text(relocations)
    (args.output / 'symbols.txt').write_text(symbols)
    selected_functions = {}
    for name in FUNCTIONS:
        text = command('aarch64-linux-gnu-objdump', '-dr', f'--disassemble={name}', str(MODULE))
        # Resolve .rodata references for human review, without changing instructions.
        annotated = []
        for line in text.splitlines():
            annotated.append(line)
            match = re.search(r'\.rodata\+0x([0-9a-f]+)', line)
            if match:
                start = int(match[1], 16)
                end = rodata.find(b'\0', start)
                if 0 <= start < len(rodata) and start <= end < start + 512:
                    raw = rodata[start:end]
                    try:
                        value = raw.decode('ascii')
                    except UnicodeDecodeError:
                        continue
                    if value and all(c.isprintable() or c in '\n\r\t' for c in value):
                        annotated.append(f'\t\t; rodata string: {value!r}')
        (args.output / f'{name}.txt').write_text('\n'.join(annotated) + '\n')
        selected_functions[name] = [
            {'text_offset': hex(start), 'bytes': length}
            for start, length, symbol in functions if symbol == name
        ]
    properties = {}
    for name in ('qcom,mdss-dsi-bl-pmic-control-type', 'qcom,bl-pmic-pwm-period-usecs',
                 'qcom,mdss-dsi-bl-ctrl-dcs-subtype', 'qcom,mdss-esync',
                 'qcom,mdss-dsi-panel-APL-THRESHOLD-BL', 'qcom,odc-enabled'):
        path = PANEL / name
        properties[name] = path.read_bytes().hex() if path.exists() else None
    report = {
        'scope': 'Offline saved target ELF and previously collected live DT; no device actions',
        'module': str(MODULE.relative_to(ROOT)),
        'module_sha256': hashlib.sha256(binary).hexdigest(),
        'module_notes': command('readelf', '-n', str(MODULE)),
        'address_space': 'ELF .text section offsets, not runtime virtual addresses',
        'pwm_external_call_sites': pwm_calls,
        'selected_functions': selected_functions,
        'selected_live_properties_hex_or_absent': properties,
        'live_esync_property_paths': [str(p.relative_to(PANEL)) for p in PANEL.rglob('*')
                                      if p.is_file() and 'esync' in p.name],
        'interpretation': 'Read the branch conditions in annotated disassembly; symbols alone do not prove OLED PWM control.',
        'physical_pwm_hz': None,
        'new_dsi_sent': False,
    }
    (args.output / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
