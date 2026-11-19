#!/usr/bin/env python3
"""Build spec_round9_20261119.json from the R9 session phase outputs (host-side).

Merges the per-phase DNG lists with the DDIC readbacks parsed from the saved
r9_ddic.sh session outputs. Output contains filenames and register values only.
Usage: gen_r9_spec.py OUT_SPEC.json EVIDENCE_DIR
"""
import json
import re
import sys
from pathlib import Path

PHASE_FILES = {
    'r9_base': ['IMG_20260502_135420612.DNG', 'IMG_20260502_135425147.DNG', 'IMG_20260502_135429640.DNG'],
    'r9_cumul': ['IMG_20260502_135459931.DNG', 'IMG_20260502_135504423.DNG', 'IMG_20260502_135508938.DNG'],
    'r9_exc80off': ['IMG_20260502_135532907.DNG', 'IMG_20260502_135537436.DNG', 'IMG_20260502_135541939.DNG'],
    'r9_exc80on': ['IMG_20260502_135551007.DNG', 'IMG_20260502_135555506.DNG', 'IMG_20260502_135600038.DNG'],
    'r9_ret': ['IMG_20260502_135713467.DNG', 'IMG_20260502_135717930.DNG', 'IMG_20260502_135722459.DNG'],
    'r9_dv1024_base': ['IMG_20260502_135746743.DNG', 'IMG_20260502_135751250.DNG', 'IMG_20260502_135755521.DNG'],
    'r9_dv1024_cumul': ['IMG_20260502_135959128.DNG', 'IMG_20260502_140003659.DNG', 'IMG_20260502_140008153.DNG'],
    'r9_dv1024_exc80off': ['IMG_20260502_140035707.DNG', 'IMG_20260502_140040218.DNG', 'IMG_20260502_140044741.DNG'],
    'r9_dv1024_exc80on': ['IMG_20260502_140054028.DNG', 'IMG_20260502_140058543.DNG', 'IMG_20260502_140103048.DNG'],
    'r9_dv512_carryover': ['IMG_20260502_140206464.DNG', 'IMG_20260502_140210976.DNG', 'IMG_20260502_140215480.DNG'],
    'r9_dv512_base': ['IMG_20260502_140322072.DNG', 'IMG_20260502_140326380.DNG', 'IMG_20260502_140330844.DNG'],
    'r9_dv512_cumul': ['IMG_20260502_140402674.DNG', 'IMG_20260502_140407156.DNG', 'IMG_20260502_140411674.DNG'],
    'r9_dv512_ret': ['IMG_20260502_140436814.DNG', 'IMG_20260502_140441266.DNG', 'IMG_20260502_140445688.DNG'],
}

OUT_MAP = {
    'r9_base': 'r9_out_base.txt', 'r9_cumul': 'r9_out_cumul.txt',
    'r9_exc80off': 'r9_out_exc80off.txt', 'r9_exc80on': 'r9_out_exc80on.txt',
    'r9_ret': 'r9_out_ret.txt',
    'r9_dv1024_base': 'r9_out_dv1024_base.txt', 'r9_dv1024_cumul': 'r9_out_dv1024_cumul.txt',
    'r9_dv1024_exc80off': 'r9_out_dv1024_exc80off.txt', 'r9_dv1024_exc80on': 'r9_out_dv1024_exc80on.txt',
    # dv512_carryover has NO readback of its own: the 3 frames were shot after the
    # BL change 1024->512 while the excursion-latched DC replica from the 1024
    # series was still active. Present the inherited register map explicitly as
    # provenance (captured at 00:52=0x04 0x00), not as this phase's measurement;
    # 00:52 at BL 512 was verified only in the subsequent (planned) phases.
    'r9_dv512_carryover': 'r9_out_dv1024_exc80on.txt',
    'r9_dv512_base': 'r9_out_dv512_base.txt', 'r9_dv512_cumul': 'r9_out_dv512_cumul2.txt',
    'r9_dv512_ret': 'r9_out_dv512_ret.txt',
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
    for phase, fname in OUT_MAP.items():
        fields = readbacks(ev / fname)
        rb[phase] = {'panelDC': 0, **fields}
    inherited = rb['r9_dv512_carryover']
    carried = {k: v for k, v in inherited.items() if k != '00:52'}
    rb['r9_dv512_carryover'] = {
        '_provenance': ('unplanned observation: frames shot after BL 1024->512 while the '
                        'excursion-latched DC replica of r9_dv1024_exc80on was still active; '
                        'no readback in this state, register map inherited from '
                        'r9_dv1024_exc80on (captured at 00:52=0x04 0x00); BL=512 verified '
                        'only in the subsequent planned phases'),
        **carried,
    }
    spec = {
        'experiment': 'ddic_round9_06x_dng_20261119',
        'panel': 'BOE ILI97701A cmd_v4 (ID 0xd2)',
        'reference_dng': 'IMG_20260502_083009182.DNG',
        'sinc_files': None,
        'fixed_conditions': {
            'refresh_hz': 120,
            'pattern': '#FFFFFF (HTMLViewer)',
            'camera': 'A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448, ISO 6400)',
            'exposure_us': 625.0,
            'esd_check_mode_restored': 'reg_read',
            'dbv_series': {'r9_': 2048, 'r9_dv1024_': 1024, 'r9_dv512_': 512},
        },
        'ddic_readbacks': rb,
        'phases': PHASE_FILES,
        'discarded_frames': {
            'r9_raw_setup_test': ['IMG_20260502_135405869.DNG'],
            'r9_dv512_rewritten_over_carryover_dc': ['IMG_20260502_140225189.DNG',
                                                     'IMG_20260502_140229630.DNG',
                                                     'IMG_20260502_140234396.DNG'],
        },
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + '\n')
    print('wrote', out_path, len(PHASE_FILES), 'phases')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: gen_r9_spec.py OUT_SPEC.json EVIDENCE_DIR')
    sys.exit(main(sys.argv[1], sys.argv[2]))
