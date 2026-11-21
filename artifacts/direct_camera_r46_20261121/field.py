"""Check the original short-measurement ROI with independent, exposure-specific CAL pairs."""
import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121.geometry import FIELDS, qualify


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path)
    ap.add_argument('--field-us', type=int, choices=(1250,4000), default=1250)
    args = ap.parse_args(); seen = set(); rows = []
    for z in ('on120A','on144B','on120C'):
        prefix = f'cal_{z}_{args.field_us}__'
        files = {i:args.frames/f'{prefix}{i}.dng' for i in (1,2)}
        if set(args.frames.glob(prefix+'*')) != set(files.values()):
            ap.error(f'{prefix}: expected two complete independent calibrations')
        rows.extend(qualify(z,args.field_us,files,seen))
    out = csv.DictWriter(sys.stdout,FIELDS,lineterminator='\n'); out.writeheader()
    for row in rows:
        out.writerow({k:format(v,'.7g') if isinstance(v,float) else v for k,v in row.items()})
    return int(any(r['status']!='PASS' for r in rows))


if __name__=='__main__':
    sys.exit(main())
