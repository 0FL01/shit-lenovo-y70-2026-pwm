#!/usr/bin/env python3
"""Offline native-command reachability and factorial identifiability audit.
Never imports a device executor and never creates a DSI program.
"""
import argparse
import itertools
import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path


def packets(blob):
    """Independent packet parser; Qualcomm 7-byte command header."""
    result, page, pos = [], None, 0
    while pos < len(blob):
        if len(blob) - pos < 7:
            raise ValueError('incomplete header')
        length = (blob[pos + 5] << 8) | blob[pos + 6]
        end = pos + 7 + length
        if not length or end > len(blob):
            raise ValueError('incomplete payload')
        payload = blob[pos + 7:end]
        selector = len(payload) == 4 and payload[:3] == bytes((255, 90, 165))
        if selector:
            page = payload[3]
        result.append({'packet': len(result), 'offset': pos, 'page': page,
                       'opcode': payload[0], 'payload': payload.hex(' '),
                       'data': payload[1:].hex(' '), 'selector': selector,
                       'header': blob[pos:pos + 7].hex(' ')})
        pos = end
    return result


def rank(rows):
    a = [[Fraction(x) for x in row] for row in rows]
    pivot = 0
    for col in range(len(a[0])):
        ix = next((i for i in range(pivot, len(a)) if a[i][col]), None)
        if ix is None:
            continue
        a[pivot], a[ix] = a[ix], a[pivot]
        divisor = a[pivot][col]
        a[pivot] = [x / divisor for x in a[pivot]]
        for i in range(len(a)):
            if i != pivot:
                multiple = a[i][col]
                a[i] = [x - multiple * y for x, y in zip(a[i], a[pivot])]
        pivot += 1
    return pivot


def design(v):
    a, d, c = v
    return [1, a, d, c, a * d, a * c, d * c, a * d * c]


def analyze(root):
    panel = root / 'artifacts/device_tree/selected_boe_v4'
    arrays = []
    for path in sorted(panel.rglob('*')):
        if not path.is_file() or 'command' not in path.name or path.name.endswith('-state'):
            continue
        try:
            parsed = packets(path.read_bytes())
        except ValueError:
            continue
        if parsed:
            arrays.append((str(path.relative_to(root)), parsed))
    if len(arrays) != 52 or sum(len(ps) for _, ps in arrays) != 1101:
        raise ValueError('selected-DT corpus differs from established 52/1101')

    points = [(0x4f, k) for k in (0x80, 0x81, 0xc0, 0xc1, 0xc8, 0xc9, 0xd0, 0xd1, 0xd8, 0xd9)]
    points += [(7, 0xec), (0x23, 0xc1)]
    native_writers = {}
    for pg, op in points:
        native_writers[f'{pg:02X}:{op:02X}'] = [
            {'path': path, **p} for path, ps in arrays for p in ps
            if not p['selector'] and (p['page'], p['opcode']) == (pg, op)]
    skeleton_points = {(8, 0x98), (0x4f, 0x81), (0x4f, 0x88), (0x4f, 0x8a), (0x4f, 0x8b)}
    skeletons = [{'path': path, 'sequence': [p for p in ps if not p['selector'] and
                   (p['page'], p['opcode']) in skeleton_points]}
                 for path, ps in arrays if any(not p['selector'] and
                   (p['page'], p['opcode']) == (0x4f, 0x81) for p in ps)]

    off_rel = 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command'
    on_rel = 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-on-command'
    off, on = (root / off_rel).read_bytes(), (root / on_rel).read_bytes()
    a_pos, d_pos = 68, 97
    delta_positions = [i for i, (x, y) in enumerate(zip(off, on)) if x != y]
    c_positions = [i for i in delta_positions if i not in (a_pos, d_pos)]
    paths = {
        '000': off_rel,
        '100': 'artifacts/dsi_selector_split_20261107/a9_only.bin',
        '010': 'artifacts/dsi_selector_split_20261107/9d_only.bin',
        '110': 'artifacts/dsi_block_trials_20261106/thresholds.bin',
        '001': 'artifacts/dsi_coupled_on_20261107/on_keep_pwm_selectors.bin',
        '111': on_rel,
        '011': 'artifacts/dsi_coupled_9d_20261107/on_keep_a9_off.bin',
    }
    binding = []
    for key, path in paths.items():
        blob = (root / path).read_bytes()
        if len(blob) != len(off):
            raise ValueError('wrong program length')
        expected = bytearray(off)
        a, d, c = map(int, key)
        for bit, positions in [(a, [a_pos]), (d, [d_pos]), (c, c_positions)]:
            if bit:
                for pos in positions:
                    expected[pos] = on[pos]
        if blob != bytes(expected):
            raise ValueError('factor binding failed for ' + path)
        ps = packets(blob)
        if len(ps) != 75 or [p['header'] for p in ps] != [p['header'] for p in packets(off)]:
            raise ValueError('changed framing')
        binding.append({'vertex_ADC': key, 'path': path,
                        'different_bytes_from_off': sum(x != y for x, y in zip(blob, off)),
                        'different_packets_from_off': sum(x['payload'] != y['payload'] for x, y in zip(ps, packets(off))),
                        'observed': key != '011'})

    # Explicit qualitative labels from reports; not inferred physical waveform/Hz.
    known = {(0, 0, 0): 0, (1, 0, 0): 1, (0, 1, 0): 0,
             (1, 1, 0): 1, (0, 0, 1): 0, (1, 1, 1): 1}
    free_vertices = [(0, 1, 1), (1, 0, 1)]
    completions = []
    for values in itertools.product((0, 1), repeat=2):
        labels = dict(known)
        labels.update(zip(free_vertices, values))
        u, v = values
        coefficients = [0, 1, 0, 0, 0, v - 1, u, 1 - v - u]
        for vertex, value in labels.items():
            if sum(x * y for x, y in zip(design(vertex), coefficients)) != value:
                raise ValueError('factor interpolation inconsistency')
        completions.append({'unobserved_011_suppressed': u, 'unobserved_101_suppressed': v,
                            'coefficients_1_A_D_C_AD_AC_DC_ADC': coefficients})

    run_path = 'artifacts/dsi_stock_on_control_20261106/with_redraw/run.json'
    run = json.loads((root / run_path).read_text())
    by_name = {s['label']: s for s in run['stages']}
    native, redraw = by_name['native_on'], by_name['native_on_redraw']
    def delta(end, start):
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    timing = {'source': run_path, 'native_on_table_verified_utc': native['transmission_verified_at_utc'],
              'same_dbv_replay_utc': native['same_dbv_replay']['at_utc'],
              'pre_redraw_hold_seconds': delta(native['hold_end_utc'], native['hold_start_utc']),
              'dbv_replay_to_pre_redraw_hold_end_seconds': delta(native['hold_end_utc'], native['same_dbv_replay']['at_utc']),
              'dbv_replay_to_post_redraw_hold_start_seconds': delta(redraw['hold_start_utc'], native['same_dbv_replay']['at_utc']),
              'new_table_sent_at_redraw': redraw['new_table_sent'],
              'logged_control_writes_during_redraw': redraw['writes_during_redraw_and_hold'],
              'limit': 'Archived host timestamps and summaries only; no raw video/trace revalidation. No sham-delay comparator; frame-update latch is a hypothesis, not identified uniquely.'}
    return {'scope': 'offline-only; exact committed corpus; no device executor',
            'source_head': 'fffb0feeda534add90dfaf7056964d40adefc183',
            'packet_arrays': len(arrays), 'packet_count': sum(len(ps) for _, ps in arrays),
            'native_writers': native_writers, 'transaction_skeletons': skeletons,
            'factor_binding': binding, 'C_changed_bytes': len(c_positions),
            'factor_model': {'response': 'binary qualitative fine-train suppression, not Hz or amplitude',
                'observed_design_rank': rank([design(v) for v in known]),
                'saturated_columns': 8, 'unobserved_vertices': ['011', '101'],
                'admissible_binary_completions': completions,
                'identifiable_011_contrast': 'beta_DC = F011 - F010 - F001 + F000; with archived qualitative labels beta_DC=F011',
                'identifiable_101_contrast': 'beta_AC = F101 - F100 - F001 + F000; with archived qualitative labels beta_AC=F101-1',
                'uniform_completion_prior_only_information_bits_each_missing_vertex': 1,
                'not_a_success_probability': True,
                'limitations': ['Six response classes are from different archived trials.',
                               'Only nominal DBV/refresh/camera context aligns; full dynamic state equivalence is not proved.',
                               'C is a 32-packet/83-byte grouped intervention, not one decoded physical register.',
                               'Binary suppression label discards residual amplitude and cannot measure PWM frequency.']},
            'redraw_timing': timing, 'pwm_hz': None, 'new_frequency_setter_found': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    result = analyze(args.root)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x') as handle:
            handle.write(rendered)
    else:
        print(rendered, end='')
