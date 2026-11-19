#!/usr/bin/env python3
"""Build the Round 8 restore cmdfile from the live r8_base snapshot (host-side).

Reads the r8_ddic.sh session output of the r8_base phase, parses every
`RD <page> <reg> <bytes...>` line, verifies the session was clean, and emits a
restore cmdfile that writes back exactly the snapshot values for every field
Round 8 overwrites (A9, 9D, 80, 95, A2 30B, 51/52, bank-wrapped F2/F3, 23 PAM
registers), followed by the full post-restore readback set.

Also gates the PAM experiment: exits non-zero if the live 23-register PAM
snapshot does not equal the stock cmd_v4 dc-off table, since r8_addpam would
then blind-overwrite unknown per-panel values.

Usage: make_r8_ret.py BASE_OUTPUT.txt OUT_R8_RET.cmd
"""
import re
import sys

PAM_OFF = {
    '5A/86': '0a 1e 04', '5A/8a': '12 2e 0f', '5A/8f': '27 3e 23', '5A/90': '0a 09 01',
    '5A/91': '09 06 00', '5A/92': '07 05 00', '5A/93': '04 02 00', '5A/94': '00 00 00',
    '5A/95': '26 24 16', '5A/9b': '00 00 00', '5A/9c': '34 3e 3c', '5A/ae': '10 2d 07',
    '5A/b3': '1c 21 22', '5A/b9': '24 1c 20', '5A/bf': '09 00 00', '5A/c0': '3a 39 3e',
    '5A/d7': '1a 20 1d', '5A/dd': '2a 27 33', '5A/e4': '32 30 3d',
    '5B/dd': '39 3a 42', '5C/c8': '08 04 06', '5C/c9': '08 04 06', '5C/ca': '00 00 00',
}
PAM_ORDER = ['5A/86', '5A/8a', '5A/8f', '5A/90', '5A/91', '5A/92', '5A/93', '5A/94',
             '5A/95', '5A/9b', '5A/9c', '5A/ae', '5A/b3', '5A/b9', '5A/bf', '5A/c0',
             '5A/d7', '5A/dd', '5A/e4', '5B/dd', '5C/c8', '5C/c9', '5C/ca']


def parse(stdout: str) -> dict:
    if 'PHASE_DONE fail=0' not in stdout or 'ESD_RESTORED reg_read' not in stdout:
        raise SystemExit('base session not clean (fail/ESD)')
    if 'ESD_ACTIVE esd_sw_sim_success' not in stdout:
        raise SystemExit('missing ESD_ACTIVE')
    snap = {}
    for line in stdout.splitlines():
        m = re.match(r'^RD (\S+) (0x[0-9A-Fa-f]+) (.+)$', line)
        if not m:
            continue
        key = f'{m.group(1)}/{m.group(2)[2:]}'.lower()
        if key in snap and snap[key] != m.group(3).strip():
            raise SystemExit(f'inconsistent reread of {key}')
        snap[key] = m.group(3).strip()
    return snap


def main(base_out: str, out_cmd: str) -> int:
    snap = parse(open(base_out).read())
    required = (['00/52', '23/a9', '23/c1', '23/80', '23/85', '24/9d', '51/a1', '51/a2',
                 '52/81', '52/82', '53/95', '53/a2', '63/f2', '63/f3']
                + [k.lower() for k in PAM_ORDER])
    missing = [k for k in required if k not in snap]
    if missing:
        raise SystemExit(f'snapshot incomplete: {missing}')
    # PAM gate: live PAM must equal the stock dc-off table before r8_addpam.
    norm = lambda s: s.lower().replace('0x', '')
    mismatch = [k for k in PAM_ORDER if norm(snap[k.lower()]) != norm(PAM_OFF[k])]
    for k in mismatch:
        print(f'PAM_MISMATCH {k} live={snap[k.lower()]} table={PAM_OFF[k]}')
    if mismatch:
        raise SystemExit(f'live PAM != stock dc-off table ({len(mismatch)} regs); '
                         'r8_addpam is NOT safe to run')
    toks = lambda s: ' '.join(b if b.startswith('0x') else '0x' + b for b in s.split())
    reg = lambda k: '0x' + k.split('/')[1].upper()
    lines = [
        'W 23 ' + reg('23/a9') + ' ' + toks(snap['23/a9']),
        'W 24 ' + reg('24/9d') + ' ' + toks(snap['24/9d']),
        'W 23 ' + reg('23/80') + ' ' + toks(snap['23/80']),
        'W 53 ' + reg('53/95') + ' ' + toks(snap['53/95']),
        'W 53 ' + reg('53/a2') + ' ' + toks(snap['53/a2']),
        'W 51 ' + reg('51/a1') + ' ' + toks(snap['51/a1']),
        'W 51 ' + reg('51/a2') + ' ' + toks(snap['51/a2']),
        'W 52 ' + reg('52/81') + ' ' + toks(snap['52/81']),
        'W 52 ' + reg('52/82') + ' ' + toks(snap['52/82']),
        'W 53 0xF0 0x01',
        'W 63 ' + reg('63/f2') + ' ' + toks(snap['63/f2']),
        'W 63 ' + reg('63/f3') + ' ' + toks(snap['63/f3']),
        'W 53 0xF0 0x00',
    ] + ['W ' + k.split('/')[0] + ' 0x' + k.split('/')[1].upper() + ' ' + toks(snap[k.lower()])
         for k in PAM_ORDER]
    reads = ['R 00 2 0x52', 'R 23 1 0xA9', 'R 23 3 0xC1', 'R 23 1 0x80', 'R 23 1 0x85',
             'R 24 1 0x9D', 'R 51 6 0xA1', 'R 51 6 0xA2', 'R 52 6 0x81', 'R 52 6 0x82',
             'R 53 2 0x95', 'R 53 30 0xA2']
    reads += ['R ' + k.split('/')[0] + ' 3 0x' + k.split('/')[1].upper() for k in PAM_ORDER]
    reads += ['W 53 0xF0 0x01', 'R 63 16 0xF2', 'R 63 16 0xF3', 'W 53 0xF0 0x00']
    with open(out_cmd, 'w') as fh:
        fh.write('\n'.join(lines + reads) + '\n')
    print(f'OK snapshot complete, PAM matches stock dc-off; wrote {out_cmd} '
          f'({len(lines)} restore writes)')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
