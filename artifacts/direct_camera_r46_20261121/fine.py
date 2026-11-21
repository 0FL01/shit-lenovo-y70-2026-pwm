#!/usr/bin/env python3
"""R46: python3 -B fine.py FRAMES > fine.csv

Native G1, fixed R42 ROI. On each DAY frame, run R44's 105..315 RAW-row
free search and two separate fixed-pitch fits. Both anchors are from R35
(initial BL 3600 triplets at 500 us): 177.35 RAW rows for 120, 188.50 for
144. Each fit recomputes its light mask and fits both sine and cosine; no
pitch, shutter phase, mask or amplitude is trained on another R46 frame.
Both nearby templates can pass on the same wave; they are not two detections.

fit_semiamp_pct is the fitted fundamental semi-amplitude, % of local light
outside broad troughs. below_empirical_gate bounds this *fitted amplitude*
by the reported gate for this image and scale, not the true modulation by a
confidence limit. not_repeated is not such a bound. Missing/unusable frames
and insufficient light intervals have no amplitude estimate. A failed free
search excludes neither other waves nor deep troughs. Only a resolved free
fit reports a measured pitch; fixed pitches are hypotheses, never detections.

Phase names are acquisition intent. Attribute a return of the fine wave to
the mode change only after verifying the 120/144/120 windows, ON, matching
HDR stimulus/drive and CAL geometry. Compare independent shutters at the
same exposure: look for repeated resolved B frames at a consistent pitch
and both A and C sensitive at that scale below the B amplitude. A B-only
free fit away from both anchors has no matched locked control here. These
spatial measurements do not yield physical Hz.
"""

import argparse
import csv
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121.fine import ARCHIVE_PITCH, EXPOSURES, assess, free_fit, inputs, load


PHASES = {f'day_{state}_{t}': EXPOSURES[t] for state in ('on120A', 'on144B', 'on120C')
          for t in ('200', '312', '500')}
ANCHORS = {'r35_177p35': ARCHIVE_PITCH, 'r35_188p50': 188.50}
METRICS = ('status', 'complete_n', 'coherent_n', 'fit_semiamp_pct', 'gate_semiamp_pct')
FIELDS = ['phase', 'frame_n', 'exposure_us', 'mean_dn', 'gate', 'free_pitch_raw',
          *(f'{name}_{key}' for name in ('free', *ANCHORS) for key in METRICS)]


def measure(paths):
    for phase, us in PHASES.items():
        frames = sorted((n, p) for (k, n), p in paths.items() if k == phase)
        for n, path in frames or [(None, None)]:
            if path is None:
                counts, data = dict(gate='missing_phase'), None
            else:
                if n < 1:
                    raise ValueError(f'{phase}: expected positive frame index')
                try:
                    counts, data = load(path, us)
                except ValueError as exc:
                    print(f'{phase}/{n}: {exc}', file=sys.stderr)
                    counts, data = dict(gate='invalid_dng'), None
            row = dict(phase=phase, frame_n=n, gate=counts['gate'],
                       exposure_us=counts.get('exposure_us'), mean_dn=counts.get('mean_dn'))
            if data is not None:
                free = free_fit(data)
                row['free_pitch_raw'] = free.get('pitch_raw')
                fits = {'free': free, **{name: assess(data, p) for name, p in ANCHORS.items()}}
            else:
                fits = {name: {'status': counts['gate']} for name in ('free', *ANCHORS)}
            for name, fit in fits.items():
                row.update({f'{name}_{key}': fit.get(key) for key in METRICS})
            yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', metavar='FRAMES', type=Path)
    args = parser.parse_args()
    try:
        has_dng = any(p.suffix.lower() == '.dng' for p in args.frames.iterdir())
        rows = list(measure(inputs(args.frames) if has_dng else {}))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
