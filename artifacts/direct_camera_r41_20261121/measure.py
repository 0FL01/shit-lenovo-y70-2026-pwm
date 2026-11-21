#!/usr/bin/env python3
"""R41: per-site camera contrast in A001 native Bayer cells [630:1370,540:720].

Usage: python measure.py FRAMES > channels.csv   (sanitized phase__N.dng)
All DN are signed after subtraction of the site's tagged BlackLevel, except
the raw clip/floor fractions (stored samples >= WhiteLevel / == 0). Dark
controls use a phase token black, dark, darks or bg, optionally numbered.
Dark, <20 DN or clipped sites retain DN diagnostics but no modulation %.

Block P05/P95 are percentiles of 5x5 same-site means. Row P01/P90 use the
horizontal mean of each block row, as in R34, but without flat correction.
Both include shading/scene gradients. R33 notch depth is relative to a local
plateau; the deepest event is selected independently for each site. Center,
FWHM and median spacing of complete <0.70-plateau runs are physical RAW rows,
not time or PWM Hz. Shading and exposure prevent interpreting these camera
contrasts as intrinsic panel modulation.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

ARTIFACTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ARTIFACTS), str(ARTIFACTS / 'direct_camera_r33_20261120'),
                str(ARTIFACTS / 'night_r113_camera_notch')]
from analyze import row_notch
from direct_camera_r34_20261120.measure import inputs
from dng_qualify import decode_dng_bytes, extract_metadata


ROI = (630, 1370, 540, 720)  # half-open, native 2x2 cells
SITES = (('R', 2), ('G1', 0), ('B', 1), ('G2', 3))  # GBRG row-major indices
DARK = re.compile(r'(?:^|_)(?:blackother|black|darks?|bg)[0-9]*(?:_|$)', re.I)


def measure(phase, n, path):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['width'], m['height'], m['orientation'],
         m['cfa_pattern_2x2'], m['focal_length_mm']) !=
            ('Nothing', 'A001', 4080, 3072, 1, [1, 2, 0, 1], 5.56)):
        raise ValueError('expected native A001 1x geometry, GBRG and 5.56 mm lens tag')
    if not (m['iso'] > 0 and np.isfinite(m['exposure_us']) and m['exposure_us'] > 0):
        raise ValueError('invalid ISO or exposure tag')

    y0, y1, x0, x1 = ROI
    for site, i in SITES:
        dy, dx = divmod(i, 2)
        stored = raw[2*y0+dy:2*y1:2, 2*x0+dx:2*x1:2]
        black, white = m['black_levels'][i], m['white_level']
        signal = stored.astype(float) - black  # do not clamp negative samples
        mean = signal.mean()
        clip, floor = (stored >= white).mean(), (stored == 0).mean()
        if DARK.search(phase):
            gate = 'dark'
        elif clip or floor:
            gate = 'clipped' if clip else 'storage_floor'
        else:
            gate = 'ok' if mean >= 20 else 'below_20dn'
        usable = gate == 'ok'

        h, w = signal.shape
        blocks = signal.reshape(h//5, 5, w//5, 5).mean(axis=(1, 3))
        p5, p95 = np.percentile(blocks, (5, 95))
        p01, p90 = np.percentile(blocks.mean(axis=1), (1, 90))
        notch = row_notch(signal, y0, usable)
        if notch['notch_center_raw_y'] is not None:
            notch['notch_center_raw_y'] += dy  # R33 returns the first row of the cell

        yield dict(phase=phase, frame_n=n, site=site, iso=m['iso'], exposure_us=m['exposure_us'],
                   focal_mm=m['focal_length_mm'], black_dn=black, white_dn=white, mean_dn=mean,
                   raw_clip_frac=clip, raw_floor_frac=floor, gate=gate,
                   block_p05_dn=p5, block_p95_dn=p95,
                   camera_block_contrast_pct=100*(p95-p5)/(p95+p5) if usable and p95+p5 > 0 else None,
                   row_p01_dn=p01, row_p90_dn=p90,
                   row_p01_dip_pct=100*(1-p01/p90) if usable and p90 > 0 else None, **notch)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', metavar='FRAMES', type=Path, help='directory of sanitized DNGs')
    args = parser.parse_args()
    try:
        paths = inputs(args.frames)
        rows = []
        for (phase, n), path in sorted(paths.items()):
            try:
                rows.extend(measure(phase, n, path))
            except ValueError as exc:
                raise ValueError(f'{phase}, frame {n}: {exc}') from exc
    except OSError as exc:
        parser.error(exc.strerror)  # keep private paths out of diagnostics
    except ValueError as exc:
        parser.error(str(exc))

    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
