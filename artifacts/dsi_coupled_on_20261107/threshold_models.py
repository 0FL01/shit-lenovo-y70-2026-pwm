#!/usr/bin/env python3
"""Falsify simple interpretations of the putative A9/AA word; no device I/O."""
import json
import operator
from pathlib import Path


def analyze():
    observations = [
        {'label': 'stock_3600', 'dbv': 3600, 'written_a9aa_be': 0x0e11, 'fine_train_present': True,
         'evidence': 'artifacts/pacman_exact_analysis_20261106.json'},
        {'label': 'stock_3601', 'dbv': 3601, 'written_a9aa_be': 0x0e11, 'fine_train_present': False,
         'evidence': 'artifacts/pacman_exact_analysis_20261106.json'},
        {'label': 'a9_only_3600', 'dbv': 3600, 'written_a9aa_be': 0x8e11, 'fine_train_present': False,
         'evidence': 'artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json'},
        {'label': '9d_only_3600', 'dbv': 3600, 'written_a9aa_be': 0x0e11, 'fine_train_present': True,
         'evidence': 'artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json'},
        {'label': 's0c1_3600', 'dbv': 3600, 'written_a9aa_be': 0x0e11, 'fine_train_present': True,
         'evidence': 'artifacts/dsi_coupled_on_20261107/analysis_spatial_v2.json'},
    ]
    decoders = {
        'unsigned_be16': lambda v: v,
        'signed_be16': lambda v: v if v < 0x8000 else v - 0x10000,
        'low15_without_control_flag': lambda v: v & 0x7fff,
        'unsigned_le16': lambda v: ((v & 255) << 8) | (v >> 8),
    }
    models = []
    for name, decode in decoders.items():
        for relation, compare in [('lt', operator.lt), ('le', operator.le), ('gt', operator.gt), ('ge', operator.ge)]:
            failures = [o['label'] for o in observations if
                        compare(o['dbv'], decode(o['written_a9aa_be'])) != o['fine_train_present']]
            models.append({'interpretation': name, 'dbv_relation_to_word': relation, 'contradictions': failures})
    survivors = [m for m in models if not m['contradictions']]
    assert [(m['interpretation'], m['dbv_relation_to_word']) for m in survivors] == [('signed_be16', 'lt')]
    forced_off = [o['label'] for o in observations if
                  (not bool(o['written_a9aa_be'] & 0x8000) and o['dbv'] < (o['written_a9aa_be'] & 0x7fff)) != o['fine_train_present']]
    assert not forced_off
    return {'scope': 'Conditional logical model audit, NOT DDIC field decoding',
        'device_io': False, 'observations': observations, 'simple_comparison_models': models,
        'also_fits': 'bit15 forces the fine-train branch off; low15 threshold otherwise',
        'unsigned_counterexample': 'At DBV3600, both 3600<3601 and 3600<36369 are true, but A9-only suppresses the fine train.',
        'assumptions': ['A9/AA is assumed to be one concatenated word; its layout is not documented.',
                        'Labels describe qualitative optical fine-train presence, not exact PWM Hz or zero residual q93 power.',
                        'Models use the written word without undocumented transformations or hidden state.'],
        'conclusion': 'Plain unsigned increasing-threshold and low15-only models fail. Signed comparison and an explicit control-bit model remain observationally indistinguishable here.',
        'pwm_hz': 'unknown', 'frequency_multiplier': None}


if __name__ == '__main__':
    result = analyze()
    with Path(__file__).with_suffix('.json').open('x') as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'models_checked': len(result['simple_comparison_models']),
                      'conclusion': result['conclusion']}))
