#!/usr/bin/env python3
"""Build spec_round12_17.json for the compensation-knob probe campaign.

Phases: R12 (53:95 interpolation at sysfs BL=256/DBV 460), R13 (PAM-block
interpolation), R14 (latch-follow test), R15 (sysfs BL event map in the
cumulative-landed state), R16 (single-knob probes at BL=512), R17 (PAM75
vs dc-on statistics at BL=460). Readbacks come from the saved session
outputs; probe cmdfiles were ad-hoc (documented inline in result.md).
Usage: gen_r1217_spec.py OUT_SPEC.json EVIDENCE_DIR
"""
import json
import re
import sys
from pathlib import Path

PHASES = {
    'r12_ref_95_4450': ['IMG_20260502_150415903.DNG', 'IMG_20260502_150419863.DNG', 'IMG_20260502_150423786.DNG', 'IMG_20260502_150427723.DNG'],
    'r12_95_3358': ['IMG_20260502_150445053.DNG', 'IMG_20260502_150449028.DNG', 'IMG_20260502_150452992.DNG', 'IMG_20260502_150456928.DNG'],
    'r12_95_2270': ['IMG_20260502_150519665.DNG', 'IMG_20260502_150523641.DNG', 'IMG_20260502_150527603.DNG', 'IMG_20260502_150531539.DNG'],
    'r12_95_1188': ['IMG_20260502_150549993.DNG', 'IMG_20260502_150553930.DNG', 'IMG_20260502_150557896.DNG', 'IMG_20260502_150601860.DNG'],
    'r12_95_00a0': ['IMG_20260502_150620992.DNG', 'IMG_20260502_150624943.DNG', 'IMG_20260502_150628917.DNG', 'IMG_20260502_150632856.DNG'],
    'r12_95_5528': ['IMG_20260502_150652126.DNG', 'IMG_20260502_150656080.DNG', 'IMG_20260502_150700028.DNG', 'IMG_20260502_150703985.DNG'],
    'r13_pam25': ['IMG_20260502_151017313.DNG', 'IMG_20260502_151021266.DNG', 'IMG_20260502_151025213.DNG', 'IMG_20260502_151029159.DNG'],
    'r13_pam50': ['IMG_20260502_151057277.DNG', 'IMG_20260502_151101250.DNG', 'IMG_20260502_151105164.DNG', 'IMG_20260502_151109139.DNG'],
    'r13_pam75': ['IMG_20260502_151128945.DNG', 'IMG_20260502_151132898.DNG', 'IMG_20260502_151136845.DNG', 'IMG_20260502_151140799.DNG'],
    'r13_pam_on_ref': ['IMG_20260502_151159989.DNG', 'IMG_20260502_151203937.DNG', 'IMG_20260502_151207880.DNG', 'IMG_20260502_151211834.DNG'],
    'r14_latch2048': ['IMG_20260502_151306911.DNG', 'IMG_20260502_151310897.DNG', 'IMG_20260502_151314852.DNG'],
    'r14_bl256_after_latch': ['IMG_20260502_151329444.DNG', 'IMG_20260502_151333378.DNG', 'IMG_20260502_151337338.DNG', 'IMG_20260502_151341289.DNG'],
    'r15_bl512': ['IMG_20260502_151430064.DNG', 'IMG_20260502_151434017.DNG', 'IMG_20260502_151437973.DNG', 'IMG_20260502_151441931.DNG'],
    'r15_bl680': ['IMG_20260502_151500857.DNG', 'IMG_20260502_151504782.DNG', 'IMG_20260502_151508761.DNG', 'IMG_20260502_151512723.DNG'],
    'r15_bl820': ['IMG_20260502_151531571.DNG', 'IMG_20260502_151535556.DNG', 'IMG_20260502_151539499.DNG', 'IMG_20260502_151543430.DNG'],
    'r15_bl1024': ['IMG_20260502_151602277.DNG', 'IMG_20260502_151606221.DNG', 'IMG_20260502_151610179.DNG', 'IMG_20260502_151614129.DNG'],
    'r15_bl1360': ['IMG_20260502_151633540.DNG', 'IMG_20260502_151637482.DNG', 'IMG_20260502_151641447.DNG', 'IMG_20260502_151645404.DNG'],
    'r15_bl1700': ['IMG_20260502_151704091.DNG', 'IMG_20260502_151708026.DNG', 'IMG_20260502_151711986.DNG', 'IMG_20260502_151715943.DNG'],
    'r16_8514': ['IMG_20260502_151822192.DNG', 'IMG_20260502_151826153.DNG', 'IMG_20260502_151830122.DNG', 'IMG_20260502_151834089.DNG'],
    'r16_4f81': ['IMG_20260502_151852248.DNG', 'IMG_20260502_151856222.DNG', 'IMG_20260502_151900199.DNG', 'IMG_20260502_151904146.DNG'],
    'r16_a2mid': ['IMG_20260502_151920711.DNG', 'IMG_20260502_151924665.DNG', 'IMG_20260502_151928627.DNG', 'IMG_20260502_151932583.DNG'],
    'r16_51a2_70': ['IMG_20260502_151949228.DNG', 'IMG_20260502_151953189.DNG', 'IMG_20260502_151957142.DNG', 'IMG_20260502_152001120.DNG'],
    'r16_9d0e': ['IMG_20260502_152017752.DNG', 'IMG_20260502_152021698.DNG', 'IMG_20260502_152025659.DNG', 'IMG_20260502_152029626.DNG'],
    'r17_pam75': ['IMG_20260502_152136483.DNG', 'IMG_20260502_152140229.DNG', 'IMG_20260502_152143996.DNG', 'IMG_20260502_152147736.DNG', 'IMG_20260502_152151484.DNG', 'IMG_20260502_152155248.DNG', 'IMG_20260502_152158998.DNG', 'IMG_20260502_152202781.DNG'],
    'r17_pamon': ['IMG_20260502_152232448.DNG', 'IMG_20260502_152236209.DNG', 'IMG_20260502_152239914.DNG', 'IMG_20260502_152243665.DNG', 'IMG_20260502_152247418.DNG', 'IMG_20260502_152251188.DNG', 'IMG_20260502_152254947.DNG', 'IMG_20260502_152258715.DNG'],
}

READBACK_MAP = {
    'r12_ref_95_4450': 'r12_out_cumul.txt', 'r12_95_3358': 'r12_out_95_3358.txt',
    'r12_95_2270': 'r12_out_95_022070.txt', 'r12_95_1188': 'r12_out_95_011088.txt',
    'r12_95_00a0': 'r12_out_95_0000a0.txt', 'r12_95_5528': 'r12_out_95_055028.txt',
    'r13_pam25': 'r13_out_pam25.txt', 'r13_pam50': 'r13_out_pam50.txt',
    'r13_pam75': 'r13_out_pam75.txt', 'r13_pam_on_ref': 'r13_out_pam_on_ref.txt',
    'r14_latch2048': 'r14_out_latch2048.txt',
    'r16_8514': 'r16_out_8514.txt', 'r16_4f81': 'r16_out_4f81.txt',
    'r16_a2mid': 'r16_out_a2mid.txt', 'r16_51a2_70': 'r16_out_51a2_70.txt',
    'r16_9d0e': 'r16_out_9d0e.txt',
    'r17_pam75': 'r17_out_pam75.txt', 'r17_pamon': 'r17_out_pamon.txt',
}
# r14_bl256_after_latch and all six r15_* phases carry NO DDIC readback of their
# own: the last register read is the r14_out_latch2048 snapshot (taken at
# 00:52=0x08 0x00); their light-level control was the per-probe sysfs check.
# They are documented with inherited context, not presented as fresh reads.
NO_READBACK_PHASES = [
    'r14_bl256_after_latch', 'r15_bl512', 'r15_bl680', 'r15_bl820',
    'r15_bl1024', 'r15_bl1360', 'r15_bl1700',
]
SYSFS_BL = {
    'r14_bl256_after_latch': 256, 'r15_bl512': 512, 'r15_bl680': 680,
    'r15_bl820': 820, 'r15_bl1024': 1024, 'r15_bl1360': 1360,
    'r15_bl1700': 1700,
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
    for phase in NO_READBACK_PHASES:
        rb[phase] = {
            'panelDC': 0,
            '_provenance': ('no DDIC readback in this phase: last register read is the '
                            'r14_out_latch2048 snapshot (00:52=0x08 0x00); light-level '
                            f'control was the per-probe sysfs check at BL={SYSFS_BL[phase]}'),
        }
    spec = {
        'experiment': 'ddic_round12_17_knobs_20261119',
        'panel': 'BOE ILI97701A cmd_v4 (ID 0xd2)',
        'reference_dng': 'IMG_20260502_083009182.DNG',
        'sinc_files': None,
        'fixed_conditions': {
            'refresh_hz': 120, 'pattern': '#FFFFFF (HTMLViewer)',
            'camera': ('A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448); UI manual ISO '
                       'was set to 6400, but ALL campaign DNGs carry EXIF ISO 3200 - '
                       'the UI setting did not take effect; all campaign-internal '
                       'comparisons share the same actual ISO 3200'),
            'exposure_us': 625.0, 'esd_check_mode_restored': 'reg_read',
            'bl_note': 'sysfs BL; readback 00:52: 256->0x01 0xcc (460), 512->0x02 0x00, 1024->0x04 0x00, 2048->0x08 0x00; BL re-asserted+verified per probe',
            'state': 'cumulative-landed DC replica unless a probe write says otherwise; '
                     '23:85=0x14 leftover from the R16 probe was present in all later '
                     'readbacks until the end-of-campaign correction',
        },
        'ddic_readbacks': rb,
        'phases': PHASES,
        'discarded_frames': {'r12_raw_setup_test': ['IMG_20260502_150401209.DNG']},
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + '\n')
    print('wrote', out_path, len(PHASES), 'phases',
          sum(len(v) for v in PHASES.values()), 'frames')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: gen_r1217_spec.py OUT_SPEC.json EVIDENCE_DIR')
    sys.exit(main(sys.argv[1], sys.argv[2]))
