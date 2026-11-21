#!/usr/bin/env python3
"""python3 -B fine.py FRAMES > fine.csv — R45 fine G1 ripple in RAW rows.

Only day_{offLow,onLow,retLow}_{200,312,500} are planned. A phase without
frames has one missing_phase row with blank counts and measurements.

free_*: R44's per-frame search (105..315 RAW rows), light mask, empirical
gate and repeat test. Only a resolved fit reports a measured pitch.
r35_*: same test at the prespecified 177.35-row pitch from the initial R35
120 Hz / BL 3600 / 500 us triplet. This tests a spatial scale in every usable
frame; it is not evidence that R45 has this pitch.
locked_*: same test at the free pitch of day_offLow_500__1, only if resolved.
As at the R35 pitch, sine and cosine can vary per frame. Neither ON nor return
can select the reference, even if the initial OFF frame is missing or fails.

phase_locked_signed_semiamp_pct: separate fit fixing BOTH pitch and fundamental
phase to that first OFF/500 frame; only the signed fundamental coefficient,
higher harmonics and segment trends are refit. Phase is relative to the first
G1 row of the fixed ROI, sin(2*pi*x/pitch + lock_phase_deg*pi/180). Independent
exposures need not share shutter phase: a small or negative signed coefficient
does not establish suppression. Use the phase-free amplitudes and their gates
for magnitude comparisons. All amplitudes are fundamental semi-amplitudes in
percent of baseline on retained light rows, not broad-trough depths or PWM Hz.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121.fine import (
    ARCHIVE_PITCH, EXPOSURES, ROI, LightFit, assess, free_fit, harmonics, inputs, load, runs_at,
)


PHASES = {f'day_{state}_{t}': EXPOSURES[t] for state in ('offLow', 'onLow', 'retLow')
          for t in ('200', '312', '500')}
REFERENCE = ('day_offLow_500', 1)
METRICS = ('status kept_cells light_runs complete_n longest_n coherent_n fit_semiamp_pct '
           'gate_semiamp_pct noise_rms_pct repeat_sem_pct').split()


def light_fit(data, pitch):
    values, _ = data
    return LightFit(values, runs_at(values[:, 0], pitch))


def signed_fit(data, pitch, direction):
    fit = light_fit(data, pitch)
    h = harmonics(fit.x, pitch)
    # Refit the restricted model: masks and per-run trends mean the sampled
    # sine/cosine need not be orthogonal, so projecting coefficients is inexact.
    basis = np.column_stack((h[:, [0, 3]] @ direction, h[:, [1, 2, 4, 5]]))
    coeff = np.linalg.lstsq(basis-fit.project(basis), fit.z[:, 0], rcond=None)[0]
    return 100*coeff[0]


def measure(paths):
    records = []
    pitch = direction = angle = None
    ref_status = 'missing_reference_frame'
    for phase, us in PHASES.items():
        found = sorted((n, p) for (k, n), p in paths.items() if k == phase)
        for n, path in found or [(None, None)]:
            if path is None:
                counts, data = dict(gate='missing_phase'), None
            else:
                if n < 1:
                    raise ValueError(f'{phase}: expected positive frame index')
                counts, data = load(path, us)
            row = dict(phase=phase, frame_n=n, phase_n=len(found) if found else None,
                       expected_us=us, roi_y0_y1_x0_x1=':'.join(map(str, ROI)), **counts)
            free = free_fit(data) if data is not None else dict(status=row['gate'])
            if (phase, n) == REFERENCE:
                ref_status = free['status']
                if ref_status == 'resolved':
                    pitch = free['pitch_raw']
                    _, c, _ = light_fit(data, pitch).fit(pitch)
                    vec = c[[0, 3], 0]
                    direction = vec/np.linalg.norm(vec)
                    angle = np.degrees(np.arctan2(direction[1], direction[0]))
            records.append((row, data, free))

    for row, data, free in records:
        skipped = dict(status=row['gate'])
        r35 = assess(data, ARCHIVE_PITCH) if data is not None else skipped
        locked = (skipped if data is None else dict(status='no_local_reference') if pitch is None
                  else assess(data, pitch))
        row.update(r35_pitch_raw=ARCHIVE_PITCH, lock_reference_status=ref_status,
                   lock_source='day_offLow_500__1' if pitch is not None else None,
                   lock_pitch_raw=pitch, lock_phase_deg=angle)
        if 'fit_semiamp_pct' in locked:
            row['phase_locked_signed_semiamp_pct'] = signed_fit(data, pitch, direction)
        for prefix, result in [('free_', free), ('r35_', r35), ('locked_', locked)]:
            row.update({prefix+k: v for k, v in result.items()})
        yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', metavar='FRAMES', type=Path)
    args = parser.parse_args()
    try:
        # Even an aborted capture with no DNGs has nine missing planned windows.
        has_dng = any(p.suffix.lower() == '.dng' for p in args.frames.iterdir())
        rows = list(measure(inputs(args.frames) if has_dng else {}))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    fields = ('phase frame_n phase_n expected_us exposure_us roi_y0_y1_x0_x1 mean_dn clip_n '
              'floor_n gate free_pitch_raw r35_pitch_raw lock_reference_status lock_source '
              'lock_pitch_raw lock_phase_deg phase_locked_signed_semiamp_pct').split()
    fields += [prefix+k for prefix in ('free_', 'r35_', 'locked_') for k in METRICS]
    writer = csv.DictWriter(sys.stdout, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
