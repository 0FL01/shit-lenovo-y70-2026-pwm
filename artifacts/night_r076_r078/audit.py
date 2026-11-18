"""Replay published phase-pair summaries only. No device, private input or network."""
import csv
from itertools import combinations_with_replacement
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ('0.97', '0', '0')
VARIANTS = {PRIMARY, ('0.95','0','0'), ('0.98','0','0'), ('0.97','4','0'),
            ('0.97','-4','0'), ('0.97','0','2'), ('0.97','0','-2')}
BOUND = ('base', '1_3600', '2_3601', '3_3602', '4_3601', '5_3600', 'restored')
DC = ('1_0', '2_1', '3_0')


def load(rows, phases):
    expected = set(combinations_with_replacement(phases, 2))
    variants = {}
    for row in rows:
        key = tuple(row[k] for k in ('ref_q','dx','dy'))
        pair = (row['a'],row['b'])
        group = variants.setdefault(key, {})
        lo, med, hi = (float(row[k]) for k in ('Dmin','Dmed','Dmax'))
        if (key not in VARIANTS or pair not in expected or pair in group or
                int(row['n']) != (3 if pair[0] == pair[1] else 9) or
                not all(math.isfinite(x) for x in (lo, med, hi)) or not 0 <= lo <= med <= hi <= 1):
            raise ValueError("invalid pair row")
        group[pair] = (lo, med, hi)
    if set(variants) != VARIANTS or any(set(g) != expected for g in variants.values()):
        raise ValueError("missing variants or pairs")
    return variants


def summarize(stem, phases, switches, controls):
    with (ROOT / ('scope_' + stem + '_divergence_20261118') / 'pairs.csv').open() as f:
        variants = load(csv.DictReader(f), phases)
    within = [(p,p) for p in phases]
    bounds = []
    for g in variants.values():
        low = min(g[p][0] for p in switches)
        high = max(g[p][2] for p in controls + within)
        bounds.append((low, high))
    g = variants[PRIMARY]
    def pair_medians(pairs):
        return {a+' -> '+b: g[(a,b)][1] for a,b in pairs}
    return {'primary_crossing_Dmed': pair_medians(switches),
            'primary_control_Dmed': pair_medians(controls),
            'primary_max_within_Dmax': max(g[p][2] for p in within),
            'min_crossing_Dmin_all_variants': min(x for x,_ in bounds),
            'max_control_or_within_Dmax_all_variants': max(y for _,y in bounds),
            'separated_variants_of_7': sum(x>y for x,y in bounds)}


def result():
    dc_args = (DC,[('1_0','2_1'),('2_1','3_0')],[('1_0','3_0')])
    return {'boundary':summarize('boundary',BOUND,
                [('1_3600','2_3601'),('4_3601','5_3600')],
                [('2_3601','3_3602'),('3_3602','4_3601'),('2_3601','4_3601'),
                 ('1_3600','5_3600'),('base','restored')]),
            'dc_3600':summarize('dc',*dc_args), 'dc_3601':summarize('dc3601',*dc_args)}


if __name__ == '__main__':
    print(json.dumps(result(), indent=2, sort_keys=True))
