#!/usr/bin/env python3
"""Offline structural follow-up of 24:91 versus the later A9/AA mechanism."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets


def arrays(text):
    result = {}
    for state in ('off', 'on'):
        m = re.search(r'^qcom,mdss-dsi-dc-' + state + r'-command\s*=\s*\[([^]]+)\];', text, re.M)
        assert m
        body = '\n'.join(line.split('//')[0] for line in m[1].splitlines())
        result[state] = parse_packets(bytes.fromhex(body))
    return result


def fields(packets):
    result = {}
    for p in packets:
        if not p['is_page_selector']:
            result.setdefault(f"{p['page']:02X}:{p['opcode']:02X}", []).append(p['data'])
    return result


def main():
    out = Path(__file__).resolve().parent
    early = Path('/home/stfu/.cache/opencode-tmp/opencode/em-large-step-20261107')
    history = Path('/home/stfu/.cache/opencode-tmp/opencode/ddic-4f-followup-20261107')
    v0, v1 = [arrays((early / f'v{i}-f088.dtsi').read_text()) for i in (0, 1)]
    patch = (history / '20b82efff00c0781ff775a1a00679c038682b974.patch').read_text()
    # The exact addition hunk creates the entire v2 source; do not treat context as added lines.
    addition = patch.split('@@ -0,0 +1,1124 @@\n', 1)[1]
    lines = [line[1:] for line in addition.splitlines() if line.startswith('+')]
    assert len(lines) == 1124
    v2 = arrays('\n'.join(lines))
    report = {'scope': 'Offline source evolution, not a write candidate or field semantics',
        'v0_v1_official_pin': 'f088523dfba85c95c15f43726fcf972c0c7a957a',
        'v2_mirror_introduction': '20b82efff00c0781ff775a1a00679c038682b974',
        'v2_source_status': 'Motorola-origin metadata in community mirror; not an authenticated official commit hash',
        'states': {}}
    for state in ('off', 'on'):
        old, new = fields(v1[state]), fields(v2[state])
        assert fields(v0[state]) == old
        assert '24:91' in old and '24:91' not in new
        assert '23:A9' not in old and '23:A9' in new and '23:AA' in new
        report['states'][state] = {'v1_packets': len(v1[state]), 'initial_v2_packets': len(v2[state]),
            'removed_fields': {k: old[k] for k in sorted(old.keys()-new.keys())},
            'added_fields': {k: new[k] for k in sorted(new.keys()-old.keys())},
            'changed_common_fields': {k: {'v1': old[k], 'v2': new[k]}
                                     for k in sorted(old.keys() & new.keys()) if old[k] != new[k]}}
    report['conclusion'] = ('24:91 disappears in the same initial v2 program that adds A9/AA, A6/A7, A2 and page63 tables, while also dropping other fields. This is a many-field revision, not evidence that 24:91 maps one-to-one to A9 or that either encodes pulse count. No numeric multiplier derived.')
    with (out / 'selector_evolution.json').open('x') as f:
        f.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
