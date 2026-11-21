#!/usr/bin/env python3
"""R44: measure GROUP_SCENE[_LABEL...]_EXPOSURE__N.dng with the R43 pipeline.

python3 -B measure.py FRAMES > frames.csv
python3 -B measure.py --summary FRAMES > summary.csv
python3 -B measure.py --summary frames.csv > summary.csv

Phase names are acquisition labels (e.g. day_off_125 or cal_on_repeat_1250).
Mean G1 DN includes every frame; event ranges include only qualified frames.
FWHM is in RAW rows; dl_us is equivalent missing plateau light, not off-time.
"""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.measure import inputs, measure


def summaries(rows):
    phases = defaultdict(list)
    for row in rows:
        phases[row['phase']].append(row)
    for phase, frames in sorted(phases.items()):
        ok = [r for r in frames if r['event_status'] == 'ok']
        out = dict(phase=phase, total=len(frames), qualified=len(ok))
        for key in ('gate', 'event_status'):
            counts = Counter(r[key] for r in frames)
            out[key + '_counts'] = ';'.join(f'{g}:{n}' for g, n in sorted(counts.items()))
        for key in ('mean_dn', 'depth_pct', 'michelson_pct', 'fwhm_raw_rows', 'dl_us'):
            values = [float(r[key]) for r in (frames if key == 'mean_dn' else ok)]
            out[key + '_min'] = min(values, default=None)
            out[key + '_max'] = max(values, default=None)
        yield out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('--summary', action='store_true', help='summarize a DNG directory or its frames.csv')
    args = ap.parse_args()
    try:
        if args.summary and args.frames.is_file():
            with args.frames.open(newline='') as f:
                rows = list(summaries(csv.DictReader(f)))
        else:
            rows = []
            for (phase, n), path in sorted(inputs(args.frames).items()):
                try:
                    rows.append(measure(phase, n, path))
                except ValueError as exc:
                    raise ValueError(f'{phase}/{n}: {exc}') from None
            if args.summary:
                rows = list(summaries(rows))
        if not rows:
            raise ValueError('no frame rows')
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
