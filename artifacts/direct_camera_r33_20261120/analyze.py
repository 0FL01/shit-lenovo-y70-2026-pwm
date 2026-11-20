#!/usr/bin/env python3
"""R33: per-frame spatial contrast on a uniform interior patch of a direct-camera DNG.

ROI bounds are half-open in native (unrotated) 2x2 Bayer cells; both extents
must be multiples of 5. Each block averages 50 green samples. Without a flat, scene texture,
vignetting and illumination gradients contribute to the percentiles, CV and deep
fraction. Compare only matched framing/ROI and exposure settings. Below 20 DN
mean, contrast ratios are noise-sensitive; a nonpositive denominator is blank.
Only the FFT removes a fitted plane; this can attenuate long-period bands and
does not remove curved shading. Its (ky,kx) are cycles across the ROI, not Hz.
Phase ordinals start at 1 in sorted phase-name order; N is the capture index.
"""

import argparse
import csv
from itertools import groupby
from pathlib import Path
import re
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "night_r113_camera_notch"))
from dng_qualify import decode_dng_bytes, extract_metadata


def spatial_peak(blocks):
    """Separate the fitted plane's corner-to-corner span from the residual peak."""
    h, w = blocks.shape
    y, x = np.arange(h) - (h - 1) / 2, np.arange(w) - (w - 1) / 2
    sy = y @ blocks.mean(axis=1) / (y @ y) if h > 1 else 0.
    sx = x @ blocks.mean(axis=0) / (x @ x) if w > 1 else 0.
    span = abs(sy) * (h - 1) + abs(sx) * (w - 1)
    residual = blocks - blocks.mean() - sy * y[:, None] - sx * x
    if min(h, w) < 3 or np.max(abs(residual)) <= 1e-12 * max(1., np.max(abs(blocks))):
        return span, None, None, None
    amp = 2 * abs(np.fft.rfft2(residual)) / blocks.size
    # A self-conjugate bin has no separate negative-frequency partner.
    for ix in ([0, w // 2] if w % 2 == 0 else [0]):
        amp[0, ix] /= 2
        if h % 2 == 0:
            amp[h // 2, ix] /= 2
        amp[h // 2 + 1:, ix] = 0  # conjugate duplicates on this axis
    amp[0, 0] = 0
    iy, ix = np.unravel_index(amp.argmax(), amp.shape)
    return span, iy if iy <= h // 2 else iy - h, ix, amp[iy, ix]


def row_notch(green, y0):
    """Local dark stripe in a sloping white field; widths/positions are sensor rows, not time."""
    empty = dict(row_notch_pct=None, notch_center_raw_y=None, notch_fwhm_raw_rows=None,
                 notch_lr_offset_raw_rows=None)
    h, w = green.shape
    if h < 90 or w < 4 or green.mean() < 20:
        return empty
    def relative(p):
        # Smooth 3 Bayer rows. Median of 81 such rows defines the local plateau;
        # broad changes are attenuated, and boundary rows are not extrapolated.
        p = np.convolve(p, np.ones(3)/3, 'valid')
        plateau = np.median(sliding_window_view(p, 81), axis=1)
        if plateau.min() <= 0:
            return None
        return p[40:-40] / plateau

    profiles = [relative(part.mean(axis=1)) for part in (green, green[:, :w//2], green[:, w//2:])]
    if any(p is None for p in profiles):
        return empty
    p, left, right = profiles
    idx = int(np.argmin(p)); depth = 1 - p[idx]
    if depth <= 0:
        return empty
    lo = hi = idx
    while lo > 0 and p[lo-1] < 1 - depth/2:
        lo -= 1
    while hi+1 < len(p) and p[hi+1] < 1 - depth/2:
        hi += 1
    # Compare the same event across the two halves, not distinct periodic minima.
    win = slice(max(0, idx-15), min(len(p), idx+16))
    return dict(row_notch_pct=100*depth, notch_center_raw_y=2*(y0+41+idx),
                notch_fwhm_raw_rows=2*(hi-lo+1) if lo > 0 and hi+1 < len(p) else None,
                notch_lr_offset_raw_rows=2*int(np.argmin(right[win])-np.argmin(left[win])))


def analyze(path, roi):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    y0, y1, x0, x1 = roi
    h, w = y1 - y0, x1 - x0
    if not (0 <= y0 < y1 <= raw.shape[0] // 2 and 0 <= x0 < x1 <= raw.shape[1] // 2):
        raise ValueError("ROI outside native Bayer-cell bounds")
    if h % 5 or w % 5:
        raise ValueError("ROI height and width must be multiples of 5 Bayer cells")

    cfa = m['cfa_pattern_2x2']
    g1, g2 = (i for i, color in enumerate(cfa) if color == 1)
    green = np.zeros((h, w))
    clipped = floor = 0
    for i in (g1, g2):
        dy, dx = divmod(i, 2)
        plane = raw[dy::2, dx::2][y0:y1, x0:x1]
        clipped += np.count_nonzero(plane >= m['white_level'])
        floor += np.count_nonzero(plane == 0)
        green += plane.astype(float) - m['black_levels'][i]
    green *= 0.5
    blocks = green.reshape(h // 5, 5, w // 5, 5).mean(axis=(1, 3))
    mean = blocks.mean()
    p5, p95 = np.percentile(blocks, (5, 95))
    span, ky, kx, peak = spatial_peak(blocks)
    return dict(width=m['width'], height=m['height'], orientation=m['orientation'],
                cfa=''.join('RGB'[n] for n in cfa), exposure_us=m['exposure_us'],
                iso=m['iso'], focal_mm=m['focal_length_mm'], white_dn=m['white_level'],
                black_g1_dn=m['black_levels'][g1], black_g2_dn=m['black_levels'][g2],
                y0=y0, y1=y1, x0=x0, x1=x1, blocks=blocks.size, green_mean_dn=mean,
                raw_green_clip_frac=clipped / (2*h*w), raw_green_zero_frac=floor / (2*h*w),
                p5_dn=p5, p95_dn=p95, p95_p5_span_dn=p95-p5,
                camera_amp_pct=100*(p95-p5)/(p95+p5) if p95+p5 > 0 else None,
                cv_pct=100*blocks.std()/mean if mean > 0 else None, subfloor_lt20=int(mean < 20),
                deep_lt065mean_frac=(blocks < 0.65*mean).mean() if mean > 0 else None,
                 plane_span_dn=span, fft_ky=ky, fft_kx=kx, fft_peak_amp_dn=peak,
                 **row_notch(green, y0))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('dir', type=Path, help='directory containing phase__N.dng files')
    p.add_argument('--roi', type=int, nargs=4, required=True, metavar=('Y0', 'Y1', 'X0', 'X1'))
    args = p.parse_args()
    frames = []
    for path in args.dir.glob('*__*.dng'):
        match = re.fullmatch(r'(.+)__([0-9]+)\.dng', path.name)
        if match and path.is_file():
            frames.append((match[1], int(match[2]), path))
    if not frames:
        p.error('no phase__N.dng inputs')
    rows = []
    for phase, (_, group) in enumerate(groupby(sorted(frames), key=lambda f: f[0]), 1):
        for _, n, path in group:
            try:
                rows.append(dict(phase_ordinal=phase, frame_n=n, **analyze(path, args.roi)))
            except (OSError, ValueError) as exc:
                p.error(f'phase {phase}, frame {n}: {exc}')
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
