#!/usr/bin/env python3
"""Generate Round 18 entry-bisection cmdfiles (host-side).

At sysfs BL=1024 the cumulative landing (shallow dips, 1.13 DN) differs from
the excursion landing (deep, 0.63 DN). These probes enter from a verified
dc-off restore with the full cumulative sequence MINUS one block each:
minus-PAM, minus-F2F3, minus-51/52. If a variant still lands shallow, the
omitted block is not required for the good landing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                        / 'ddic_round9_06x_dng_20261119'))
from gen_r9_cmdfiles import CORE_ON, FULL_READS  # noqa: E402


def is_pam(line: str) -> bool:
    p = line.split()
    return len(p) >= 2 and p[0] == 'W' and p[1] in ('5A', '5B', '5C')


def is_f2f3(line: str) -> bool:
    p = line.split()
    if len(p) < 2 or p[0] != 'W':
        return False
    if p[1] == '53' and p[2] == '0xF0':
        return True
    return p[1] == '63' and p[2] in ('0xF2', '0xF3')


def is_5152(line: str) -> bool:
    p = line.split()
    return len(p) >= 2 and p[0] == 'W' and p[1] in ('51', '52')


VARIANTS = {
    'r18_minus_pam': lambda l: not is_pam(l),
    'r18_minus_f2f3': lambda l: not is_f2f3(l),
    'r18_minus_5152': lambda l: not is_5152(l),
}


def main(outdir: str) -> int:
    base = Path(outdir)
    base.mkdir(parents=True, exist_ok=True)
    for tag, keep in VARIANTS.items():
        writes = [l for l in CORE_ON if keep(l)]
        lines = writes + FULL_READS
        (base / f'{tag}.r18').write_text('\n'.join(lines) + '\n')
        print(base / f'{tag}.r18', len(lines), 'lines',
              f'(writes: {len(writes)})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
