"""Export the successful R34 window log, bound to the two SF snapshots and actual DNG tags."""
import argparse
from collections import defaultdict
import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import sys

# The R33 file is also called windows.py, so do not resolve through an ambiguous import name.
spec = spec_from_file_location('r33_windows', Path(__file__).resolve().parents[1]/'direct_camera_r33_20261120/windows.py')
r33 = module_from_spec(spec)
spec.loader.exec_module(r33)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('frames_csv', type=Path)
    args = ap.parse_args()
    groups = defaultdict(list)
    with args.frames_csv.open() as f:
        for r in csv.DictReader(f):
            groups[r['phase']].append(r)
    out = csv.writer(sys.stdout, lineterminator='\n')
    out.writerow(('phase', 'profile', 'scene_rgb', 'sysfs_bl', 'hwc_pre', 'hwc_post', 'sf_rgb_pre',
                  'sf_rgb_post', 'exposure_us', 'frames'))
    for line in (args.archive/'windows.log').read_text().splitlines():
        m = re.fullmatch(r'WINDOW (\w+) (active|stock|92|9e|a9) (512) hwcId=(0) color=([0-9a-f]{6}) ns=(\d+) count=(\d+)', line)
        if not m:
            raise ValueError('unexpected window receipt')
        phase, profile, bl, hwc, rgb, ns, count = m.groups()
        rows = groups.pop(phase); exp = int(ns)/1000
        if sorted(int(r['frame_n']) for r in rows) != list(range(1,int(count)+1)):
            raise ValueError(f'{phase}: capture count mismatch')
        if any(abs(float(r['exposure_us'])/exp-1)>.001 or r['iso']!='6400' or r['focal_mm']!='5.56' or
               (r['width'], r['height'], r['orientation']) != ('4080','3072','1') for r in rows):
            raise ValueError(f'{phase}: DNG metadata mismatch')
        pre,a = r33.sf(args.archive/f'{phase}-pre.sf'); post,b = r33.sf(args.archive/f'{phase}-post.sf')
        if (pre,post)!=(hwc,hwc):
            raise ValueError(f'{phase}: HWC mismatch')
        out.writerow((phase,profile,rgb,bl,pre,post,a,b,exp,count))
    if set(groups) != {'pilot'} or len(groups['pilot']) != 1:
        raise ValueError('unbound frames outside pilot')
    out.writerow(('pilot','geometry','ffffff',6692,'','','','',200,1))


if __name__ == '__main__':
    main()
