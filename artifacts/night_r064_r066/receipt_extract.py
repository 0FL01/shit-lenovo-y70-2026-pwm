"""Offline optional projection. Emits only validated numerical rows, never raw dumps."""
import json
import re
import sys
from pathlib import Path


def extract(first_run, boundary):
    rows = []
    with (first_run / 'log.jsonl').open() as src:
        for line in src:
            _, key, obj = json.loads(line)
            if key != 'reach':
                continue
            arg, early, late = obj
            if not (late['policy'] == 'BRIGHT' and late['reason'] == 'manual'
                    and late['user'] == late['out'] and str(early) == late['DBV']
                    and all(re.fullmatch(r'0\.\d{1,12}', s) for s in (arg, late['user']))):
                raise ValueError('unqualified calibration row')
            rows.append([arg, late['user'], int(late['android']), int(early)])
    curves = {l.strip() for l in (first_run / 'display_initial.txt').read_text().splitlines()
              if l.strip().startswith('mBrightnessToBacklightSpline=')}
    if len(curves) != 1:
        raise ValueError('ambiguous spline')
    knots = [list(map(float, m)) for m in
             re.findall(r'\(([\d.]+), ([\d.]+): ([\d.]+)\)', curves.pop())]
    segments = [[a,b] for a,b in zip(knots,knots[1:]) if a[0] <= .14 <= .15 <= b[0]]
    if len(segments) != 1:
        raise ValueError('no unique calibration segment')
    direct = []
    for p in json.loads(boundary.read_text())['phases']:
        pair = []
        for end in ('start', 'end'):
            s = p[end]
            if not (s['actual_brightness'] == '0' and s['dc'] == '0'
                    and s['manual'] == '0' and s['bl_power'] == '0'
                    and s['provider'] == 'Result: Bundle[{value=0}]'):
                raise ValueError('direct path guard')
            m = re.fullmatch(r'\s*mBrightnessState=(0\.\d+)', s['float'])
            if not m:
                raise ValueError('missing float')
            pair.append([int(s['brightness']), m[1], int(s['android']), int(s['max_brightness'])])
        if pair[0] != pair[1]:
            raise ValueError('direct start/end mismatch')
        direct.append(pair[0])
    return {'android_calibration':rows, 'spline_segment':segments[0], 'native_direct':direct}


if __name__ == '__main__':
    print(json.dumps(extract(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
