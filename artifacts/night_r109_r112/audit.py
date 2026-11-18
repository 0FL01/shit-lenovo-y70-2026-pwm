"""Re-score four potential photographic singletons from the published aggregate matrix."""
import csv
import json
from decimal import Decimal
from itertools import combinations_with_replacement
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / 'scope_dc3601_divergence_20261118' / 'matrix.csv'
SIZES = {'3600:0': 6, '3600:1': 3, '3601:0': 6, '3601:1': 3}
VARIANTS = {('0.97','0','0'), ('0.95','0','0'), ('0.98','0','0'),
            ('0.97','-4','0'), ('0.97','4','0'), ('0.97','0','-2'), ('0.97','0','2')}


def score(rows):
    pairs = set(combinations_with_replacement(sorted(SIZES), 2))
    table = {}
    for row in rows:
        k = tuple(row[c] for c in ('ref_q', 'dx', 'dy'))
        a, b = sorted((row['dbv_dc_a'], row['dbv_dc_b']))
        if k not in VARIANTS or (a, b) not in pairs or (a, b) in table.setdefault(k, {}):
            raise ValueError('unexpected or duplicate variant/cell')
        n = SIZES[a]*SIZES[b] if a != b else SIZES[a]*(SIZES[a]-1)//2
        ds = [Decimal(row[c]) for c in ('Dmin', 'Dmed', 'Dmax')]
        if int(row['n']) != n or not all(d.is_finite() and 0 <= d <= 1 for d in ds) or ds != sorted(ds):
            raise ValueError('unexpected pair count or bounds')
        table[k][a, b] = (ds[0], ds[2])
    if set(table) != VARIANTS or any(set(cells) != pairs for cells in table.values()):
        raise ValueError('incomplete input')
    out = {}
    for x in sorted(SIZES):
        gaps = {}
        for k, cells in sorted(table.items()):
            change = [v[0] for p, v in cells.items() if p.count(x) == 1]
            rest = [v[1] for p, v in cells.items() if p.count(x) != 1]
            gaps[','.join(k)] = min(change) - max(rest)
        floor = min(gaps.values())
        out[x] = {'gaps_by_q_dx_dy': {k: format(v, '.6f') for k,v in gaps.items()},
                  'worst_gap': format(floor, '.6f'), 'separated': floor > 0}
    return out


if __name__ == '__main__':
    with MATRIX.open(newline='') as f:
        print(json.dumps(score(csv.DictReader(f)), indent=2, sort_keys=True))
