#!/usr/bin/env python3
"""R44: python3 -B geometry.py FRAMES > geometry.csv

Require cal_{off,on,ret}_1250__{1,2}.dng. Additional suffixed scenes (e.g.
on120) need their own 1250 us pair. Only an independent, passing 500 us pair
of the exact same scene can replace a clipped pair. R43's guarded ROI and
field checks qualify illumination, not the switch state or PWM frequency.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.geometry import qualify


CAL = re.compile(r'cal_((?:off|on|ret)[A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)_(1250|500)__([12])\.dng')
FIELDS = ('scene exposure_us y0 y1 x0 x1 guard clip1 clip2 floor1 floor2 quarter first_y last_y '
          'field_p75_dn1 field_p75_dn2 lit_frac1 lit_frac2 lateral_bad_rows1 lateral_bad_rows2 '
          'uncovered_rows min_pair_score worst_y worst_window_x0 status').split()


def run(frames):
    groups = {}
    for p in sorted(frames.iterdir()):
        if not p.name.startswith('cal_') or p.suffix.lower() not in ('.dng', '.partial'):
            continue
        m = CAL.fullmatch(p.name)
        if not m or p.is_symlink() or not p.is_file():
            raise ValueError(f'invalid or unfinished CAL: {p.name}')
        groups.setdefault((m[1], int(m[2])), {})[int(m[3])] = p

    scenes = {'off', 'on', 'ret'} | {scene for scene, _ in groups}
    for scene in sorted(scenes):
        if (scene, 1250) not in groups:
            raise ValueError(f'{scene}/1250: missing primary CAL pair')
    seen, rows = set(), []  # shared across scenes and shutters to reject reused RAW patches
    for scene in sorted(scenes):
        primary = None
        for us in (1250, 500):
            pair = groups.get((scene, us))
            if pair is None:
                continue
            if set(pair) != {1, 2}:
                raise ValueError(f'{scene}/{us}: expected __1 and __2')
            try:
                result = qualify(scene, us, pair, seen)
            except ValueError as exc:
                raise ValueError(f'{scene}/{us}: {exc}') from None
            rows.extend(result)
            if us == 1250:
                primary = result[0]
            elif primary['status'] == 'CLIPPED' and all(r['status'] == 'PASS' for r in result):
                primary['status'] = 'CLIPPED_REPLACED_BY_500'
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    try:
        rows = run(args.frames)
    except (OSError, ValueError) as exc:
        ap.exit(1, f'FAIL: {exc}\n')
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.7g') if isinstance(v, float) else v for k, v in row.items()})
    return int(any(r['status'] not in ('PASS', 'CLIPPED_REPLACED_BY_500') for r in rows))


if __name__ == '__main__':
    sys.exit(main())
