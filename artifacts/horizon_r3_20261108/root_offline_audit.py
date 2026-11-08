#!/usr/bin/env python3
"""Offline evidence/design audit. Never imports a device runner or calls processes.

Recomputes only published summary arithmetic, not raw video or live behavior.
The Boolean witnesses illustrate non-identifiability; they are not DDIC models.
"""
import argparse
import ast
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = 'fffb0feeda534add90dfaf7056964d40adefc183'


def read_json(relative):
    return json.loads((ROOT / relative).read_text())


def rank(rows):
    a = [[Fraction(x) for x in row] for row in rows]
    r = 0
    for c in range(len(a[0])):
        pivot = next((i for i in range(r, len(a)) if a[i][c]), None)
        if pivot is None:
            continue
        a[r], a[pivot] = a[pivot], a[r]
        divisor = a[r][c]
        a[r] = [x / divisor for x in a[r]]
        for i in range(len(a)):
            if i != r:
                factor = a[i][c]
                a[i] = [x - factor * y for x, y in zip(a[i], a[r])]
        r += 1
        if r == len(a):
            break
    return r


def summary_recompute(relative):
    d = read_json(relative)
    out = []
    for i, s in enumerate(d['stages']):
        if 'normalized_q_ratio_to_adjacent_stock' not in s:
            continue
        selected = d['stages'][i - 1:i + 2]
        q = [v['q93_total_rms_Y_codes'] / (v['raw_mean_Y'] - 16) for v in selected]
        ratio = q[1] / ((q[0] + q[2]) / 2)
        recorded = s['normalized_q_ratio_to_adjacent_stock']
        if abs(ratio - recorded) > 1e-12:
            raise ValueError(f'Summary normalization mismatch: {relative} {s["label"]}')
        out.append({'stage': s['label'], 'ratio_recomputed': ratio,
                    'ratio_recorded': recorded, 'absolute_error': abs(ratio - recorded),
                    'input_json_pointer': f'/stages/{i}'})
    return {'source': relative, 'raw_video_redecoded': False, 'results': out}


def audit():
    panel = ROOT / 'artifacts/device_tree/selected_boe_v4'
    off = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
    on = (panel / 'qcom,mdss-dsi-dc-on-command').read_bytes()
    candidate_dir = ROOT / 'artifacts/dsi_coupled_9d_20261107'
    candidate = (candidate_dir / 'on_keep_a9_off.bin').read_bytes()
    expected = on[:68] + off[68:69] + on[69:]
    if candidate != expected or not len(candidate) == len(off) == len(on) == 875:
        raise ValueError('Candidate no longer matches its exact historical definition')
    validation = read_json('artifacts/dsi_coupled_9d_20261107/validation.json')
    hashes = {name: hashlib.sha256(data).hexdigest()
              for name, data in [('stock', off), ('candidate', candidate)]}
    if hashes['stock'] != validation['stock_sha256'] or hashes['candidate'] != validation['candidate_sha256']:
        raise ValueError('Candidate/return identity changed')
    if any((candidate_dir / name).exists() for name in ('authorization.json', 'run.json')):
        raise ValueError('Authorization/run state changed; review before regenerating this report')

    # Codes are qualitative historical outcomes from proposal.md:12-20.
    # 1 = fine-image train suppressed, not high PWM and not a measured Hz value.
    known = {(0, 0, 0): 0, (1, 0, 0): 1, (0, 1, 0): 0,
             (1, 1, 0): 1, (1, 1, 1): 1, (0, 0, 1): 0}
    cells = list(itertools.product((0, 1), repeat=3))
    unknown = [cell for cell in cells if cell not in known]
    design = [[1, a, d, c, a*d, a*c, d*c, a*d*c] for a, d, c in known]
    witnesses = {
        'A_only': lambda a, d, c: a,
        'A_or_D_and_C': lambda a, d, c: int(a or (d and c)),
        'A_and_D_or_not_C': lambda a, d, c: int(a and (d or not c)),
    }
    witness_results = []
    for name, function in witnesses.items():
        agrees = all(function(*cell) == y for cell, y in known.items())
        if not agrees:
            raise ValueError('Illustrative witness does not match the stated qualitative cells')
        witness_results.append({'name': name, 'agrees_with_all_six_qualitative_cells': agrees,
                                'missing_cell_predictions': [
                                    {'A_D_C': list(cell), 'suppression': function(*cell)}
                                    for cell in unknown]})

    source = (ROOT / '06-tools/run_dsi_mode_trial.py').read_text()
    module = ast.parse(source)
    probe_nodes = [n for n in module.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'PROBES' for t in n.targets)]
    if len(probe_nodes) != 1:
        raise ValueError('Unexpected runner probe definition')
    probes = ast.literal_eval(probe_nodes[0].value)
    watched = [value.split()[1].split(':', 1)[1] for value in probes.values()]
    symbols = (ROOT / 'artifacts/runtime_pwm_recon_20261107/evidence/symbols.txt').read_text().splitlines()
    names = ['sde_encoder_phys_cmd_trigger_start', 'sde_encoder_helper_trigger_start',
             'sde_hw_ctl_trigger_start', '_sde_encoder_phys_cmd_config_autorefresh']
    symbol_rows = []
    for name in names:
        matches = [(i, line) for i, line in enumerate(symbols, 1) if line.split()[-1:] == [name]]
        symbol_rows.append({'symbol': name, 'archive_matches': [
            {'line': i, 'record': line} for i, line in matches],
            'body_reverified_from_target_elf': False})

    summaries = [summary_recompute(relative) for relative in [
        'artifacts/dsi_selector_split_20261107/analysis_spatial_v2.json',
        'artifacts/dsi_coupled_on_20261107/analysis_spatial_v2.json',
        'artifacts/dsi_block_trials_20261106/with_redraw/analysis_spatial_v2.json']]
    return {
        'base_commit': PIN, 'device_io': False, 'physical_pwm_hz': None,
        'greater_equal_2000_hz_verified': False,
        'candidate_identity': {'bytes': len(candidate), 'hashes': hashes,
            'changed_offsets_from_native_on': [i for i, (a, b) in enumerate(zip(on, candidate)) if a != b],
            'changed_byte_count_from_stock': sum(a != b for a, b in zip(off, candidate)),
            'authorization_present': False, 'run_present': False,
            'scope_source': 'artifacts/dsi_coupled_9d_20261107/proposal.md'},
        'qualitative_design': {'source': 'artifacts/dsi_coupled_9d_20261107/proposal.md:12-24',
            'known_cell_count': len(known), 'unobserved_cells': [list(c) for c in unknown],
            'saturated_design_rank': rank(design), 'saturated_parameter_count': 8,
            'unrestricted_boolean_completions': 2 ** len(unknown), 'witnesses': witness_results,
            'limits': ['Historical runs are not a randomized simultaneous factorial trial.',
                      'Suppression is a qualitative image outcome, not an emission-frequency result.',
                      'No probability distribution over Boolean completions is justified.',
                      'Stock versus A0D1C1 changes 33 packets; a positive result identifies a profile effect, not 9D alone.']},
        'archived_summary_arithmetic': summaries,
        'control_logger_coverage': {'runner_probes': probes, 'watched_functions': watched,
            'frame_kickoff_is_a_runner_probe': any('kickoff' in s or 'trigger_start' in s for s in watched),
            'source_semantic_check': 'root_cadence.md', 'target_archived_symbols': symbol_rows,
            'limits': ['Symbol presence does not prove the reference source matches the target function body.',
                      'No saved pixel-transfer cadence, TE edges or physical emission timebase is recovered by this audit.']},
        'unmaterialized_inputs': [str(p.relative_to(ROOT)) for p in [
            ROOT / 'artifacts/kernel/gki_r59/target_vendor/msm_drm.ko',
            ROOT / 'artifacts/optical/pacman_dsi_selector_split_20261107.mp4',
            ROOT / '05-safety/optical_measurement.md'] if not p.exists()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(audit(), ensure_ascii=False, indent=2) + '\n'
    if args.output is None:
        print(text, end='')
    else:
        with args.output.open('x') as handle:
            handle.write(text)


if __name__ == '__main__':
    main()
