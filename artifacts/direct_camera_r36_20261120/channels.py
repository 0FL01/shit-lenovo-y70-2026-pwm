#!/usr/bin/env python3
"""R36 white 125 us: same-event depths on individual native A001 Bayer sites.

Run: python3 -B channels.py /path/to/R36/frames > channels.csv
white.csv fixes the event before inspecting R or B. Its raw y labels the first
row of a 2x2 cell; the paired greens sample its midpoint y+0.5 on average.
Use R33's three-cell row smoother and median of the surrounding 81 smoothed
cells as a local plateau, separately for each site. Linearly interpolate at
the common physical row for depth; never move the depth sample to a site min.
The local min and midpoint of the two half-depth crossings within +/-30 RAW
rows are separate alignment diagnostics. A broad bottom can have a noisy min.
Units are sensor rows, not time. Bayer passbands overlap; white-field results
are not separate measurements of the three OLED primaries or a tint trial.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'night_r113_camera_notch'))
from dng_qualify import decode_dng_bytes, extract_metadata


PHASES = ('mid_125', 'peak_125', 'midret_125')
ROI = (630, 1370, 540, 720)  # half-open Bayer cells, in white.csv order
SITES = ('G1', 'B', 'R', 'G2')  # validated GBRG, row-major


def characterize(rows, profile, event):
    """All rows are physical RAW coordinates of three-cell smoothed samples."""
    k = int(np.argmin(abs(rows - event)))
    if not 40 <= k < len(rows) - 40:
        raise ValueError('green event lacks a complete local plateau window')
    plateau = np.median(profile[k-40:k+41])
    if plateau <= 0:
        raise ValueError('nonpositive local plateau')
    at_event = np.interp(event, rows, profile)
    inside = abs(rows - event) <= 30
    x, p = rows[inside], profile[inside]
    i = int(np.argmin(p))
    # Require a bounded dip actually containing the green event, so an
    # unrelated local minimum cannot masquerade as the center of this stripe.
    half = (plateau + p[i]) / 2
    center = None
    if at_event < half and p[i] < plateau:
        left = np.flatnonzero(p[:i] >= half)
        right = np.flatnonzero(p[i+1:] >= half)
        if left.size and right.size:
            l, r = left[-1], i + 1 + right[0]
            xl = np.interp(half, p[[l+1, l]], x[[l+1, l]])
            xr = np.interp(half, p[r-1:r+1], x[r-1:r+1])
            if xl < event < xr:
                center = (xl + xr) / 2
    return plateau, at_event, 100 * (1 - at_event / plateau), x[i] - event, center


def measure(path, ref):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['focal_length_mm'], m['exposure_us'], m['iso'],
         m['orientation'], m['width'], m['height'], m['cfa_pattern_2x2']) !=
            ('Nothing', 'A001', 5.56, 125, 6400, 1, 4080, 3072, [1, 2, 0, 1])):
        raise ValueError('wrong camera, exposure or CFA geometry')
    if tuple(int(ref[k]) for k in ('y0', 'y1', 'x0', 'x1')) != ROI:
        raise ValueError('published ROI mismatch')
    y0, y1, x0, x1 = ROI
    first_y = int(ref['notch_center_raw_y'])
    if first_y % 2:
        raise ValueError('expected cell-origin y in white.csv')
    event = first_y + 0.5
    sites = []
    for i, name in enumerate(SITES):
        dy, dx = divmod(i, 2)
        plane = raw[2*y0+dy:2*y1:2, 2*x0+dx:2*x1:2]
        black = m['black_levels'][i]
        signal = plane.mean(axis=1) - black  # signed, no black-floor clamp
        profile = np.convolve(signal, np.ones(3)/3, 'valid')
        clip = np.count_nonzero(plane >= m['white_level'])
        zero = np.count_nonzero(plane == 0)
        gate = 'clipped' if clip or zero else 'below_20dn' if signal.mean() < 20 else 'ok'
        data = dict(phase=ref['phase'], frame_n=ref['frame_n'], site=name, black_dn=black,
                    mean_dn=signal.mean(), clip_n=clip, zero_n=zero, gate=gate)
        sites.append((data, profile))

    # Reproduce the published green depth from these raw sites at the locked
    # cell before accepting the anchor (also detects a mislabelled frame).
    even_y = 2 * np.arange(y0+1, y1-1)
    if any(sites[i][0]['gate'] != 'ok' for i in (0, 3)):
        raise ValueError('unqualified green reference')
    green = (sites[0][1] + sites[3][1]) / 2
    _, _, green_depth, _, green_center = characterize(even_y + 0.5, green, event)
    if green_center is None or abs(green_depth - float(ref['row_notch_pct'])) > 1e-5:
        raise ValueError('green event inconsistent with white.csv')

    for i, (data, profile) in enumerate(sites):
        plateau = at = depth = min_offset = center = offset = None
        if data['gate'] == 'ok':
            plateau, at, depth, min_offset, center = characterize(even_y + i//2, profile, event)
            if center is not None:
                offset = center - green_center
        yield dict(**data, fixed_green_raw_y=event, local_plateau_dn=plateau,
                   dn_at_green=at, depth_at_green_pct=depth, local_min_minus_fixed_rows=min_offset,
                   green_half_center_raw_y=green_center, site_half_center_raw_y=center,
                   half_center_minus_green_rows=offset)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path)
    args = ap.parse_args()
    with (HERE / 'white.csv').open() as f:
        refs = [r for r in csv.DictReader(f) if r['phase'] in PHASES]
    expected = [(ph, n) for ph in PHASES for n in (1, 2, 3)]
    indexed = {(r['phase'], int(r['frame_n'])): r for r in refs}
    if set(indexed) != set(expected) or len(refs) != len(expected):
        ap.error('incomplete or duplicate white reference rows')
    rows = []
    for ph, n in expected:  # read exactly the nine designated inputs
        try:
            rows.extend(measure(args.frames / f'{ph}__{n}.dng', indexed[ph, n]))
        except (ValueError, OSError) as exc:
            ap.error(f'{ph}/{n}: {exc.strerror if isinstance(exc, OSError) else exc}')
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: round(v, 6) if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
