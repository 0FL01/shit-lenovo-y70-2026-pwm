#!/usr/bin/env python3
"""Bind the complete R38 native ON → 30/120 history → OFF → repeat ON acquisition.

Usage: python windows.py ARCHIVE FRAMES_CSV [LOG ...] > windows.csv
Default transcript: run.log. The match file selects a captured trial code;
admission is not a claim that its optical error was within five percent.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re


spec = spec_from_file_location('r37_windows', Path(__file__).resolve().parents[1] /
                               'direct_camera_r37_20261120/windows.py')
r37 = module_from_spec(spec)
spec.loader.exec_module(r37)
need = r37.need

TRIAL = re.compile(r'pick([1-5])_g([1-9][0-9]{0,2})')


def protocol(picks, k):
    """Insertion order is the run.sh acquisition order, including the OFF proof."""
    policy = {}

    def add(phase, dc, ns, count, gray):
        policy[phase] = r37.Policy('0', '2048' if dc else '512', str(dc), ns, count, f'{gray:02x}' * 3)

    def sample(prefix, dc, gray):
        for suffix, ns, count in [('black', 25000000, 3), ('flat', 25000000, 3),
                                  ('short', 4000000, 4), ('other', 6666667, 3)]:
            add(f'{prefix}_{suffix}', dc, ns, count, 0 if suffix == 'black' else gray)

    sample('ref', 0, 255)
    add('white10', 1, 1250000, 3, 255)
    add('match_black', 1, 25000000, 2, 0)
    need(1 <= len(picks) <= 5 and picks[0] == 'pick1_g140', 'missing or invalid initial gray trial')
    codes = []
    for i, phase in enumerate(picks, 1):
        m = TRIAL.fullmatch(phase)
        need(m and int(m[1]) == i and 1 <= int(m[2]) <= 254, 'invalid gray trial index/code')
        codes.append(int(m[2]))
        add(phase, 1, 25000000, 2, codes[-1])
    need(k in codes, 'selected gray was not captured in a trial')
    sample('native10', 1, k)
    sample('history06', 1, k)
    add('white06', 1, 1250000, 3, 255)
    add('offproof', 0, 4000000, 2, 255)
    sample('repeat10', 1, k)
    sample('refret', 0, 255)
    return policy


def bind(archive, frames_csv, logs):
    token = (archive / 'match').read_text().strip()
    need(re.fullmatch(r'[1-9][0-9]{0,2}', token) and int(token) <= 254, 'invalid match code')
    # Ordered progress of this run, not phase ordinals (measure.py sorts lexically).
    steps, endpoints, picks, fits = [], [], [], []
    for log in logs:
        with (archive / log).open() as stream:
            for raw in stream:
                line = raw.strip()
                if (m := r37.SNAP.fullmatch(line)) and m[1] in ('init', 'restored'):
                    steps.append(m[1])
                    endpoints.append(m.group(6, 10, 11))  # wake, F81, C1 at DBV 3601
                elif line.startswith('WINDOW '):
                    phase = line.split()[1]
                    steps.append(phase)
                    if TRIAL.fullmatch(phase):
                        picks.append(phase)
                elif line.startswith('FIT '):
                    m = re.fullmatch(r'FIT (\w+) gross=\S+ bg=\S+ target=\S+ best=([1-9][0-9]{0,2}) err=\S+', line)
                    need(m and steps and m[1] == steps[-1] and TRIAL.fullmatch(m[1]) and
                         any(TRIAL.fullmatch(p)[2] == m[2] for p in picks), 'unbound gray fit receipt')
                    steps.append('FIT ' + m[1])
                    fits.append(m[2])

    policy = protocol(picks, int(token))
    expected = ['init']
    for ph in policy:
        expected.append(ph)
        if TRIAL.fullmatch(ph):
            expected.append('FIT ' + ph)
    need(steps == [*expected, 'restored'] and fits[-1:] == [token], 'incomplete or reordered R38 run or wrong match')
    need(endpoints[0] == endpoints[1] and endpoints[0][2] == '000010', 'initial/final stock readback mismatch')
    epoch, seed, _ = endpoints[0]

    rows = r37.bind(archive, frames_csv, logs, policy)
    for row in rows:
        rec = dict(zip(r37.COLUMNS, row))
        ph = rec['phase']
        if ph == 'pilot':  # R37 has independently checked the labelled geometry-only DNG, if present.
            continue
        dc = policy[ph].dc
        need(rec['wake_epoch'] == epoch and rec['C1'] == ('000010' if dc == '1' else '0002be'),
             f'{ph}: wake or native C1 alpha mismatch')
        if ph != 'offproof':  # this window proves the intervening OFF core; it does not select F81
            f81 = seed if dc == '0' else ('06' if ph.startswith('history06_') or ph == 'white06' else '10')
            need(rec['F81'] == f81, f'{ph}: incorrect native F81 history')

    for suffix in (['on', 'ret'] if seed == '06' else ['on']):
        r37.mode(archive / f'mode30_{suffix}.sf', '6')
        r37.mode(archive / f'mode120_{suffix}.sf', '0')
    return rows


if __name__ == '__main__':
    r37.main(bind, 'run.log', __doc__)
