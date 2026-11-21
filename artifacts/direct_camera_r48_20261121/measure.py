#!/usr/bin/env python3
"""R48: python3 -B measure.py FRAMES [--orientation {1,6}] > frames.csv

Measure the stored Bayer plane with R44's native ROI and metrics. The resumed
capture has TIFF Orientation 6; selecting that tag does not rotate the plane.
"""

import argparse
from contextlib import contextmanager
import csv
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.geometry import EXPECTED_ORIENTATION
from direct_camera_r44_20261121 import measure as r44


def add_orientation(parser):
    parser.add_argument('--orientation', choices=(1, 6), type=int, default=1,
                        help='required TIFF Orientation tag (default: 1); always use native sensor axes')


@contextmanager
def native_orientation(value):
    token = EXPECTED_ORIENTATION.set(value)
    try:
        yield
    finally:
        EXPECTED_ORIENTATION.reset(token)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--summary', action='store_true', help='summarize a DNG directory or its frames.csv')
    add_orientation(ap)
    args = ap.parse_args()
    try:
        with native_orientation(args.orientation):
            if args.summary and args.frames.is_file():
                with args.frames.open(newline='') as stream:
                    frames = list(csv.DictReader(stream, strict=True))
                if any(r['orientation'] != str(args.orientation) for r in frames):
                    raise ValueError('frames.csv orientation differs from --orientation')
            else:
                frames = []
                for (phase, n), path in sorted(r44.inputs(args.frames).items()):
                    try:
                        frames.append(r44.measure(phase, n, path))
                    except ValueError as exc:
                        raise ValueError(f'{path.name}: {exc}') from None
            rows = list(r44.summaries(frames)) if args.summary else frames
            if not rows:
                raise ValueError('no frame rows')
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
