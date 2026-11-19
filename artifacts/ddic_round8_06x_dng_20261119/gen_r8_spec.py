#!/usr/bin/env python3
"""Build spec_round8_20261119.json from the session phase outputs (host-side).

Merges the per-phase DNG lists with the DDIC readbacks parsed from the saved
r8_ddic.sh session outputs in the private evidence directory. Output contains
filenames and register values only (no serials/paths from the private dir).
"""
import json
import re
import sys
from pathlib import Path

PHASE_FILES = {
    'r8_base': ['IMG_20260502_131219127.DNG', 'IMG_20260502_131223641.DNG', 'IMG_20260502_131228189.DNG'],
    'r8_a9a2': ['IMG_20260502_131258452.DNG', 'IMG_20260502_131302985.DNG', 'IMG_20260502_131307493.DNG'],
    'r8_add9d': ['IMG_20260502_131438385.DNG', 'IMG_20260502_131442924.DNG', 'IMG_20260502_131447762.DNG'],
    'r8_add80': ['IMG_20260502_131511117.DNG', 'IMG_20260502_131515649.DNG', 'IMG_20260502_131520476.DNG'],
    'r8_add95': ['IMG_20260502_131543983.DNG', 'IMG_20260502_131548515.DNG', 'IMG_20260502_131553364.DNG'],
    'r8_add5152': ['IMG_20260502_131616267.DNG', 'IMG_20260502_131620816.DNG', 'IMG_20260502_131625338.DNG'],
    'r8_ctl_80off': ['IMG_20260502_131716735.DNG', 'IMG_20260502_131721280.DNG', 'IMG_20260502_131725794.DNG'],
    'r8_ctl_80on': ['IMG_20260502_131757209.DNG', 'IMG_20260502_131801642.DNG', 'IMG_20260502_131806496.DNG'],
    'r8_addf23': ['IMG_20260502_132005410.DNG', 'IMG_20260502_132009934.DNG', 'IMG_20260502_132014774.DNG'],
    'r8_addpam': ['IMG_20260502_132055798.DNG', 'IMG_20260502_132100791.DNG', 'IMG_20260502_132105381.DNG'],
    'r8_ret': ['IMG_20260502_132302383.DNG', 'IMG_20260502_132307298.DNG', 'IMG_20260502_132311849.DNG'],
}

OUT_MAP = {
    'r8_base': 'r8_out_base.txt', 'r8_a9a2': 'r8_out_a9a2.txt', 'r8_add9d': 'r8_out_add9d.txt',
    'r8_add80': 'r8_out_add80.txt', 'r8_add95': 'r8_out_add95.txt', 'r8_add5152': 'r8_out_add5152.txt',
    'r8_ctl_80off': 'r8_out_ctl_80off.txt', 'r8_ctl_80on': 'r8_out_ctl_80on.txt',
    'r8_addf23': 'r8_out_addf23.txt', 'r8_addpam': 'r8_out_addpam.txt', 'r8_ret': 'r8_out_ret.txt',
}

def readbacks(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r'^RD (\S+) (0x[0-9A-Fa-f]+) (.+?)\s*$', line)
        if not m:
            continue
        page, reg, val = m.group(1), m.group(2), m.group(3)
        key = f'{page}:{reg[2:].upper()}'
        out[key] = val.replace('0x', '')
    # 51:A2 vs 53:A2 collision: page distinguishes them already.
    return out


def main(out_path: str, evidence_dir: str) -> int:
    ev = Path(evidence_dir)
    rb = {}
    for phase, fname in OUT_MAP.items():
        rb[phase] = readbacks(ev / fname)
        rb[phase]['panelDC'] = 0
    # Post-shots convenience note: report tables use the spec ddic_readbacks directly.
    spec = {
        'experiment': 'ddic_round8_06x_dng_20261119',
        'panel': 'BOE ILI97701A cmd_v4 (ID 0xd2)',
        'reference_dng': 'IMG_20260502_083009182.DNG',
        'sinc_files': None,
        'fixed_conditions': {
            'refresh_hz': 120,
            'pattern': '#FFFFFF (HTMLViewer)',
            'camera': 'A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448, ISO 6400)',
            'exposure_us': 625.0,
            'esd_check_mode_restored': 'reg_read',
        },
        'ddic_readbacks': rb,
        'phases': PHASE_FILES,
        'discarded_frames': {
            'r8_addf23_dv828_retry': ['IMG_20260502_131854063.DNG', 'IMG_20260502_131858915.DNG',
                                      'IMG_20260502_131903428.DNG'],
            'r8_ret_first_attempt_failed_restore': ['IMG_20260502_132135862.DNG',
                                                    'IMG_20260502_132140807.DNG',
                                                    'IMG_20260502_132145456.DNG'],
        },
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + '\n')
    print('wrote', out_path, len(PHASE_FILES), 'phases')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: gen_r8_spec.py OUT_SPEC.json EVIDENCE_DIR')
    sys.exit(main(sys.argv[1], sys.argv[2]))
