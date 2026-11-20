"""Bind R33 DNG phase ordinals to the sanitized acquisition windows and actual SF modes."""
import argparse
import csv
import re
import sys

from pathlib import Path


def sf(path):
    text = path.read_text()
    modes = set(re.findall(r'activeMode=\{id=\d+, hwcId=(\d+),', text))
    if len(modes) != 1:
        raise ValueError('ambiguous/missing HWC mode')
    matrix = re.search(r'colorTransformMatrix=\[(\[.*?\])\]', text)
    values = list(map(float, re.findall(r'-?\d+\.\d+', matrix[0]))) if matrix else []
    # SF prints four adjacent bracketed rows, then the closing matrix bracket.
    if len(values) != 16:
        raise ValueError('unexpected color matrix')
    return modes.pop(), '/'.join(f'{values[i]:.3f}' for i in (0, 5, 10))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('logs', nargs='+', help='private acquisition logs in chronological order')
    args = p.parse_args()
    groups = {}
    for path in (args.archive/'frames').glob('*__*.dng'):
        phase, index = path.stem.rsplit('__', 1)
        groups.setdefault(phase, []).append(int(index))
    phases = sorted(groups)
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(('phase_ordinal', 'phase', 'profile', 'scene_rgb', 'sysfs_bl', 'hwc_pre', 'hwc_post',
                'sf_rgb_pre', 'sf_rgb_post', 'frames'))
    seen = set()
    for name in args.logs:
        color = None
        for line in (args.archive/name).read_text().splitlines():
            if m := re.fullmatch(r'scene ([0-9a-f]{6}) \(.*\)', line):
                color = m[1]
            if m := re.fullmatch(r'WINDOW (\w+) (active|stock) BL=(\d+) hwcId=(\d+) count=(\d+)', line):
                phase, profile, bl, hwc, count = m.groups()
                if not color or phase in seen or sorted(groups[phase]) != list(range(1,int(count)+1)):
                    raise ValueError('incomplete or duplicated phase')
                pre, a = sf(args.archive/f'{phase}-pre.sf')
                post, b = sf(args.archive/f'{phase}-post.sf')
                if pre != hwc or post != hwc:
                    raise ValueError('mode mismatch')
                w.writerow((phases.index(phase)+1, phase, profile, color, bl, pre, post, a, b, count))
                seen.add(phase)
    if set(phases)-seen != {'pilot'}:
        raise ValueError('unbound capture groups (other than pilot)')
    w.writerow((phases.index('pilot')+1, 'pilot', 'geometry only', 'ffffff', 6692, '', '', '', '', 1))


if __name__ == '__main__':
    main()
