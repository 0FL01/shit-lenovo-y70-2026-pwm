#!/usr/bin/env python3
"""Build spec_round10_20261119.json from the Round 10 session (host-side).

Round 10 has two parts at sysfs BL=256 (DDIC readback 00:52=0x01 0xcc = 460,
the documented DT minimum): (1) the floor probe (PWM base, fresh cumulative
dc-on replica, snapshot restore — BL verified per phase); (2) the exposure
sweep of the cumulative-landed state with sysfs BL verified immediately
before AND after every shot pair. The first sweep attempt was invalidated by
slider-control loss and mid-sweep drift; an intermediate second series (10
frames, no per-pair BL checks) was superseded by the final per-pair-checked
series; both excluded series are listed under discarded_frames.
Output contains filenames and register values only.
Usage: gen_r10_spec.py OUT_SPEC.json EVIDENCE_DIR
"""
import json
import re
import sys
from pathlib import Path

PHASE_FILES = {
    'r10_dv256_base': ['IMG_20260502_142005471.DNG', 'IMG_20260502_142009799.DNG', 'IMG_20260502_142014244.DNG'],
    'r10_dv256_cumul': ['IMG_20260502_142038399.DNG', 'IMG_20260502_142042831.DNG', 'IMG_20260502_142047233.DNG'],
    'r10_dv256_ret': ['IMG_20260502_142109564.DNG', 'IMG_20260502_142114018.DNG', 'IMG_20260502_142118436.DNG'],
    'r10_sweep125': ['IMG_20260502_144040387.DNG', 'IMG_20260502_144044314.DNG'],
    'r10_sweep500': ['IMG_20260502_144105165.DNG', 'IMG_20260502_144109079.DNG'],
    'r10_sweep625': ['IMG_20260502_144127654.DNG', 'IMG_20260502_144131564.DNG'],
    'r10_sweep800': ['IMG_20260502_144150574.DNG', 'IMG_20260502_144154498.DNG'],
    'r10_sweep1562': ['IMG_20260502_144238370.DNG', 'IMG_20260502_144242277.DNG'],
    'r10_sweep12500': ['IMG_20260502_144315618.DNG', 'IMG_20260502_144319557.DNG'],
}

OUT_MAP = {
    'r10_dv256_base': 'r10_out_dv256_base.txt', 'r10_dv256_cumul': 'r10_out_dv256_cumul.txt',
    'r10_dv256_ret': 'r10_out_dv256_ret.txt',
}

DISCARDED = {
    'r10_raw_setup_test': ['IMG_20260502_141952170.DNG'],
    'r10_sweep_attempt1_uncontrolled_light': [
        'IMG_20260502_142411332.DNG', 'IMG_20260502_142428169.DNG', 'IMG_20260502_142432558.DNG',
        'IMG_20260502_142459259.DNG', 'IMG_20260502_142503719.DNG', 'IMG_20260502_142527006.DNG',
        'IMG_20260502_142531378.DNG', 'IMG_20260502_142554477.DNG', 'IMG_20260502_142558837.DNG',
        'IMG_20260502_142621617.DNG', 'IMG_20260502_142625920.DNG', 'IMG_20260502_142648575.DNG',
        'IMG_20260502_142406924.DNG',
    ],
    # Intermediate series 2: dumpsys-verified exposures but no per-pair BL checks;
    # pair-level inconsistencies vs the accepted series (e.g. 800us pair 1.01/1.02
    # there vs 0.52/1.03 in v3) -> superseded, not mixed into the accepted sample.
    'r10_sweep_attempt2_no_per_pair_bl_check': [
        'IMG_20260502_143236472.DNG', 'IMG_20260502_143240579.DNG', 'IMG_20260502_143253972.DNG',
        'IMG_20260502_143258096.DNG', 'IMG_20260502_143320229.DNG', 'IMG_20260502_143324348.DNG',
        'IMG_20260502_143354088.DNG', 'IMG_20260502_143358200.DNG', 'IMG_20260502_143420028.DNG',
        'IMG_20260502_143424130.DNG',
    ],
}

SWEEP_CUMUL_READBACK = 'r10_out_sweep2_cumul.txt'
FINAL_RET_READBACK = 'r10_out_final_ret.txt'


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
    for phase, fname in OUT_MAP.items():
        rb[phase] = {'panelDC': 0, **readbacks(ev / fname)}
    for phase in ('r10_sweep125', 'r10_sweep500', 'r10_sweep625', 'r10_sweep800',
                  'r10_sweep1562', 'r10_sweep12500'):
        # All sweep pairs were shot in the r10_sweep2_cumul state (fresh cumulative
        # dc-on replica at DBV 256); BL=256 verified before and after every pair.
        rb[phase] = {'panelDC': 0, **readbacks(ev / SWEEP_CUMUL_READBACK)}
    spec = {
        'experiment': 'ddic_round10_06x_dng_20261119',
        'panel': 'BOE ILI97701A cmd_v4 (ID 0xd2)',
        'reference_dng': 'IMG_20260502_083009182.DNG',
        'sinc_files': None,
        'fixed_conditions': {
            'refresh_hz': 120,
            'pattern': '#FFFFFF (HTMLViewer)',
            'camera': 'A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448, ISO 6400)',
            'esd_check_mode_restored': 'reg_read',
            'dbv_note': ('sysfs BL=256 maps to DDIC readback 00:52=0x01 0xcc (460, the '
                         'documented DT minimum); panel DBV is 460, not 256'),
            'bl_check': ('sysfs 256 verified before and after every sweep pair; sweep '
                         'phases share one readback from the state-entry transaction'),
        },
        'ddic_readbacks': rb,
        'phases': PHASE_FILES,
        'discarded_frames': DISCARDED,
        'final_restore_readback': FINAL_RET_READBACK,
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + '\n')
    print('wrote', out_path, len(PHASE_FILES), 'phases')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: gen_r10_spec.py OUT_SPEC.json EVIDENCE_DIR')
    sys.exit(main(sys.argv[1], sys.argv[2]))
