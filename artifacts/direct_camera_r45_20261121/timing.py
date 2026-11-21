#!/usr/bin/env python3
"""Audit whether R43 threshold spacings identify *broad* troughs at low drive.

python3 -B timing.py FRAMES                     # R45 short windows
python3 -B timing.py --on-blur FRAMES           # R43 exposure fit only in R45 ON
python3 -B timing.py --r35-control R35_FRAMES     # historical failure case

All gaps are untyped R43 observations in RAW rows. R44's free pitch is fitted
to the same DNG; a gap within 10% of it is compatible with ONE fine cycle,
not a broad-period observation. A mismatch or unresolved pitch does not
identify a broad interval either. Nothing is pooled across shutters/states.

The R45 identity test fixes the R42/R43 qualified deepest G1 center first.
At that row and +/- one fine pitch, linearly interpolate valid 3-cell G1
means, full width and in each horizontal half. Use only this frame's free
pitch if resolved; otherwise the fixed R35 control cannot establish local
fine phase. No search for better references or a substitute center. Require
>=20 DN on each flank. Cap reference difference at 10% of their mean (each
reference then lies within 5% of the denominator). Require BOTH deficits to
exceed 1 DN, 3*sqrt(2)*local split-column RMS and the reference difference;
repeat against the least reference within one native cell of each location
to guard interpolation sensitivity. This is an empirical screen, not a CI.
The two halves check the same single event, not independent replicates.
Depths are signed fractions against the stated references, never off-time.

Separately test the NECESSARY geometry for a PAIR of identified troughs:
span between two such centers <= (last G1 row - first G1 row) - 2*fine pitch,
even before reserving the trough width and its shoulders. Count R43 runs
whose full bounds and shoulders would have both references inside the ROI.
This is coverage only, not proof of an extra deficit. No edge extrapolation.
For illustration, in the R45 ROI a pitch like R35's 177.35 would leave
1238 - 2*177.35 = 883.3 RAW rows, less than R35's observed ~1065-row
broad spacing. This is a design limit at those pitches, not R45 evidence.

For timing one would additionally need isolated residual shapes under both
shutters: the broad event, not the carrier, must identify the commuting-box
gradient, stable to pitch/mask changes, in >=2 independent DNGs per shutter
of the same qualified state. Two same-frame, adjacent, identified troughs in
>=2 DNGs are separately required for a repeat interval. Even then this is a
conditional broad recurrence, not the physical fine PWM frequency. Neither a
prior high-drive gradient nor HWC cadence supplies the missing measurement.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r35_20261120.spacing import ROI as CONTROL_ROI
from direct_camera_r42_20261121.measure import ROI, decode_dng_bytes, extract_metadata, fixed_event, inputs, row_notch, sample
from direct_camera_r43_20261121.timing import spacing
from direct_camera_r44_20261121.fine import ARCHIVE_PITCH, EXPOSURES, free_fit


FIELDS = ('phase frame exposure_us roi_cells_y0_y1_x0_x1 mean_g1_dn gate '
          'r43_runs_n r43_untyped_gaps_raw fine_status fine_pitch_raw '
          'gaps_near_one_fine_cycle_n runs_with_both_reference_windows_n '
          'max_two_center_span_raw id_anchor_status id_status id_pitch_source id_pitch_raw '
          'id_center_raw_y id_minus_raw_y id_plus_raw_y').split()
ID_FIELDS = ('status minus_dn center_dn plus_dn noise_gate_dn depth_vs_minus_frac '
             'depth_vs_plus_frac depth_vs_mean_frac').split()
FIELDS += [f'id_{name}_{key}' for name in ('full', 'left', 'right') for key in ID_FIELDS]


def probe(part, rows, event, pitch):
    """Native G1 rows only, no clamping at the ROI edge, no recentering."""
    box = np.ones(3)/3
    p = np.convolve(part.mean(1), box, 'valid')
    ref = np.array([event-pitch, event+pitch])
    out = {key: np.interp(r, rows, p) for key, r in zip(('minus_dn', 'center_dn', 'plus_dn'),
                                                          (ref[0], event, ref[1])) if rows[0] <= r <= rows[-1]}
    # Need observed rows for both amplitude and local noise, not just centers.
    if ref[0]-12 < rows[0] or ref[1]+12 > rows[-1]:
        return dict(out, status='reference_window_outside_roi')
    minus, center, plus = out['minus_dn'], out['center_dn'], out['plus_dn']
    a, b = part[:, ::2], part[:, 1::2]
    diff = (a.mean(1)-b.mean(1)) * np.sqrt(a.shape[1]*b.shape[1])/part.shape[1]
    noise = np.convolve(diff, box, 'valid')
    # +/-6 Bayer cells, max over all three neighborhoods. Sensitivity to
    # column texture is included. sqrt(2) covers differencing two levels.
    rms = max(np.sqrt(np.mean(noise[abs(rows-r) <= 12]**2)) for r in (*ref, event))
    gate = max(1., 3*np.sqrt(2)*rms)
    out['noise_gate_dn'] = gate
    bg = (minus+plus)/2
    spread = abs(minus-plus)
    if min(minus, plus) < 20:
        return dict(out, status='reference_below_20dn')
    if spread > .10*bg:
        return dict(out, status='inconsistent_references')
    # Include all piecewise-linear knots, not just the endpoints of the shift.
    low = min(min(np.interp([r-2, r+2], rows, p).min(), p[abs(rows-r) <= 2].min()) for r in ref)
    if low < 20 or low-center <= max(gate, spread):
        return dict(out, status='insufficient_robust_excess')
    return dict(out, status='ok', depth_vs_minus_frac=1-center/minus,
                depth_vs_plus_frac=1-center/plus, depth_vs_mean_frac=1-center/bg)


def identity(g, fine):
    pitch = fine.get('pitch_raw') if fine['status'] == 'resolved' else None
    local = pitch is not None
    if not local:
        pitch = ARCHIVE_PITCH
    out = dict(id_pitch_raw=pitch, id_pitch_source='same_frame_free' if local else 'fixed_R35_control_only')
    anchor = row_notch(g, ROI[0], True)['notch_center_raw_y']
    mid = g.shape[1]//2
    parts = {'full': g, 'left': g[:, :mid], 'right': g[:, mid:]}
    # Same full-width anchor and all three fixed-event qualifications as R43.
    # sample() has already rejected any storage-floor or clipped G1 sample.
    for name, part in parts.items():
        status = ('no_candidate' if anchor is None else 'below_20dn' if part.mean() < 20
                  else fixed_event(part, 0, anchor)[0])
        if status != 'ok':
            return dict(out, id_anchor_status=f'{name}:{status}', id_status='unqualified_anchor')
    out.update(id_anchor_status='ok', id_center_raw_y=anchor, id_minus_raw_y=anchor-pitch,
               id_plus_raw_y=anchor+pitch)
    rows = 2*np.arange(ROI[0]+1, ROI[1]-1)
    failed = []
    for name, part in parts.items():
        result = probe(part, rows, anchor, pitch)
        out.update({f'id_{name}_{k}': v for k, v in result.items()})
        if result['status'] != 'ok':
            failed.append(f"{name}:{result['status']}")
    out['id_status'] = (';'.join(failed) if failed else 'excess_at_local_pitch' if local
                        else 'excess_at_R35_control_only')
    return out


def audit(path, roi, us):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['iso'], m['focal_length_mm'], m['orientation'],
         m['cfa_pattern_2x2'], raw.shape) != ('Nothing', 'A001', 6400, 5.56, 1, [1, 2, 0, 1], (3072, 4080))
            or not abs(m['exposure_us'] - us) <= .001):
        raise ValueError(f'{path.name}: unexpected camera mode or exposure')
    y0, y1, x0, x1 = roi
    g, q = sample(raw[2*y0:2*y1:2, 2*x0:2*x1:2], m['black_levels'][0], m['white_level'], False)
    row = dict(exposure_us=m['exposure_us'], roi_cells_y0_y1_x0_x1=':'.join(map(str, roi)),
               mean_g1_dn=q['mean_dn'], gate=q['gate'])
    if q['gate'] != 'ok':
        return dict(row, id_status=q['gate'])
    runs, gaps, _ = spacing(g)
    row.update(r43_runs_n=len(runs), r43_untyped_gaps_raw=';'.join(f'{v:g}' for v in gaps))
    # R44 free fit, also for the R35 control in its own qualified ROI.
    p = g.mean(axis=1)
    x = np.linspace(-1, 1, len(p))
    shade = np.polyval(np.polyfit(x, p, 2), x)
    if not np.all(np.isfinite(shade) & (shade > 0)):
        fine = dict(status='invalid_shading')
    else:
        a, b = g[:, ::2], g[:, 1::2]
        noise = (a.mean(1)-b.mean(1)) * np.sqrt(a.shape[1]*b.shape[1])/g.shape[1]
        fine = free_fit((np.column_stack((p, noise))/shade[:, None], shade))
    row['fine_status'] = fine['status']
    if fine['status'] == 'resolved':
        pitch = fine['pitch_raw']
        # runs uses the valid 3-cell-smoothed signal with 10-cell shoulders;
        # include the extra native cell needed to evaluate the smoothing.
        margin = 11 + pitch/2
        row.update(fine_pitch_raw=pitch,
                   gaps_near_one_fine_cycle_n=sum(abs(dx/pitch-1) <= .10 for dx in gaps),
                   runs_with_both_reference_windows_n=sum(a >= margin and b+margin <= len(g)-1 for a, b in runs),
                   max_two_center_span_raw=max(0, 2*(len(g)-1)-2*pitch))
    return dict(row, **identity(g, fine)) if roi == ROI else dict(row, id_status='not_R45_ROI')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path)
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--r35-control', action='store_true', help='initial h120 BL3600 312.5/500 us, R35 ROI')
    modes.add_argument('--on-blur', action='store_true', help='R43 independent scale and recurrence gates on measured ON without resolved fine ripple')
    args = ap.parse_args()
    if args.on_blur:
        from direct_camera_r43_20261121 import timing as r43
        out = csv.DictWriter(sys.stdout, r43.FIELDS, lineterminator='\n')
        out.writeheader()
        for row in r43.analyze(args.frames, {'onLow': {k: r43.US[k] for k in ('200', '312', '500')}}):
            out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})
        return
    roi = CONTROL_ROI if args.r35_control else ROI
    pattern = r'h120_b3600_t(312|500)' if args.r35_control else r'day_(?:offLow|onLow|retLow)_(200|312|500)'
    rows = []
    try:
        for (phase, n), path in sorted(inputs(args.frames).items()):
            match = re.fullmatch(pattern, phase)
            if not match:
                continue
            if n <= 0:
                raise ValueError('frame indices must be positive')
            rows.append(dict(phase=phase, frame=n, **audit(path, roi, EXPOSURES[match[1]])))
        if not rows:
            raise ValueError('no matching short windows')
        if args.r35_control and {(r['phase'], r['frame']) for r in rows} != {
                (f'h120_b3600_t{t}', n) for t in ('312', '500') for n in (1, 2, 3)}:
            raise ValueError('incomplete R35 control triplets')
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
