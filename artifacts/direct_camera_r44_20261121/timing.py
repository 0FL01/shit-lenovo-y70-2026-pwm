"""Run R43's existing spacing/blur gates independently per high-drive R44 switch state.

Use the same accepted archive as windows.py, after optical/dispatch qualification.
No refresh-rate input or transfer of phase scale between ON and OFF. Low-drive
ripples are not treated as independent recurrences of the broad high-drive dip.
"""
import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.timing import FIELDS, US, analyze


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path)
    args = ap.parse_args()
    shutters = {t: US[t] for t in ('125', '200', '312')}
    out = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator='\n')
    out.writeheader()
    for row in analyze(args.frames, dict.fromkeys(('off', 'on', 'ret'), shutters)):
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
