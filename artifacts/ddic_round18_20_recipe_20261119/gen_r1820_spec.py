#!/usr/bin/env python3
"""Build spec_round18_20.json for the entry-bisection & minimal-recipe rounds.

Phases: R18 (cumulative entry minus one block each, sysfs BL=1024),
R19 (core 5/3/2 minimization), R20 (core3 at BL=460, core3 re-applied from
the deep core2 state, 3-write restore to PWM).
Usage: gen_r1820_spec.py OUT_SPEC.json EVIDENCE_DIR
"""
import json
import re
import sys
from pathlib import Path

PHASES = {
    'r18_minus_pam': ['IMG_20260502_152417247.DNG', 'IMG_20260502_152421218.DNG', 'IMG_20260502_152425177.DNG', 'IMG_20260502_152429106.DNG'],
    'r18_minus_f2f3': ['IMG_20260502_152452743.DNG', 'IMG_20260502_152456706.DNG', 'IMG_20260502_152500647.DNG', 'IMG_20260502_152504574.DNG'],
    'r18_minus_5152': ['IMG_20260502_152527606.DNG', 'IMG_20260502_152531577.DNG', 'IMG_20260502_152535531.DNG', 'IMG_20260502_152539450.DNG'],
    'r19_core5': ['IMG_20260502_152628802.DNG', 'IMG_20260502_152632745.DNG', 'IMG_20260502_152636707.DNG', 'IMG_20260502_152640659.DNG'],
    'r19_core3': ['IMG_20260502_152701345.DNG', 'IMG_20260502_152705246.DNG', 'IMG_20260502_152709172.DNG', 'IMG_20260502_152713057.DNG'],
    'r19_core2': ['IMG_20260502_152733070.DNG', 'IMG_20260502_152736951.DNG', 'IMG_20260502_152740863.DNG', 'IMG_20260502_152744778.DNG'],
    'r20_core3_460': ['IMG_20260502_152828622.DNG', 'IMG_20260502_152832541.DNG', 'IMG_20260502_152836479.DNG', 'IMG_20260502_152840387.DNG'],
    'r20_core3_reapply_from_core2': ['IMG_20260502_152913166.DNG', 'IMG_20260502_152917051.DNG', 'IMG_20260502_152920973.DNG', 'IMG_20260502_152924867.DNG'],
    'r20_ret3_pwm': ['IMG_20260502_152941419.DNG', 'IMG_20260502_152945356.DNG', 'IMG_20260502_152949257.DNG'],
}

READBACK_MAP = {
    'r18_minus_pam': 'r18_out_minus_pam.txt', 'r18_minus_f2f3': 'r18_out_minus_f2f3.txt',
    'r18_minus_5152': 'r18_out_minus_5152.txt',
    'r19_core5': 'r19_out_core5.txt', 'r19_core3': 'r19_out_core3.txt',
    'r19_core2': 'r19_out_core2.txt',
    'r20_core3_460': 'r20_out_core3_460.txt',
    'r20_core3_reapply_from_core2': 'r20_out_core3_reapply.txt',
    'r20_ret3_pwm': 'r20_out_ret3.txt',
}


def readbacks(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r'^RD (\S+) (0x[0-9A-Fa-f]+) (.+?)\s*$', line)
        if not m:
            continue
        key = f'{m.group(1)}:{m.group(2)[2:].upper()}'
        out[key] = m.group(3).replace('0x', '')
    return out


def main(out_path: str, evidence_dir: str) -> int:
    ev = Path(evidence_dir)
    rb = {}
    for phase, fname in READBACK_MAP.items():
        rb[phase] = {'panelDC': 0, **readbacks(ev / fname)}
    spec = {
        'experiment': 'ddic_round18_20_recipe_20261119',
        'panel': 'BOE ILI97701A cmd_v4 (ID 0xd2)',
        'reference_dng': 'IMG_20260502_083009182.DNG',
        'sinc_files': None,
        'fixed_conditions': {
            'refresh_hz': 120, 'pattern': '#FFFFFF (HTMLViewer)',
            'camera': ('A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448); UI manual ISO '
                       'was set to 6400, but all campaign DNGs carry EXIF ISO 3200; '
                       'all campaign-internal comparisons share that actual ISO'),
            'exposure_us': 625.0, 'esd_check_mode_restored': 'reg_read',
            'bl_note': 'R18/R19 at sysfs 1024 (00:52=0x04 0x00); R20 at sysfs 256 (0x01 0xcc=460); fresh snapshot restore before every entry',
            'entry_note': 'every phase entered from a verified dc-off snapshot restore',
        },
        'ddic_readbacks': rb,
        'phases': PHASES,
        'recipe_candidate': {
            'apply_shortest_tested': ['W 23:A9=0x8e', 'W 24:9D=0x8e', 'W 23:80=0x90'],
            'restore': ['W 23:A9=0x0e', 'W 24:9D=0x0e', 'W 23:80=0x50'],
            'verified_at_sysfs_bl': [256, 1024],
        },
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + '\n')
    print('wrote', out_path, len(PHASES), 'phases',
          sum(len(v) for v in PHASES.values()), 'frames')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: gen_r1820_spec.py OUT_SPEC.json EVIDENCE_DIR')
    sys.exit(main(sys.argv[1], sys.argv[2]))
