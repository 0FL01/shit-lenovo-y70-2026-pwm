"""Remove smooth fixed shading using the same scene/HWC/BL/profile at 25 ms.

This measures camera contrast at the short exposure, not optical modulation at all frequencies.
"""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

from analyze import read_patch


def frames(directory, name, usec):
    files = sorted(directory.glob(name+'__*.dng'))
    if len(files) < 3:
        raise ValueError('need at least three independent shutter releases')
    for path in files:
        m, green, clipped, _ = read_patch(path, (630, 1370, 540, 720))
        if ((m['width'], m['height'], m['orientation']) != (4080, 3072, 1) or
                m['focal_length_mm'] != 5.56 or m['iso'] != 6400 or clipped or
                abs(m['exposure_us']-usec) > 0.001*usec):
            raise ValueError('rejected geometry/gain/exposure or saturation: '+name)
        yield green.reshape(148, 5, 36, 5).mean(axis=(1, 3))


def measure(writer, phase, index, blocks, flat):
    if flat.min() < 20:
        raise ValueError('reference blocks below signal floor')
    if blocks.mean() < 20:
        writer.writerow((phase, index, round(blocks.mean(), 3), '', '', ''))
        return
    x = blocks/flat
    p5, p95 = np.percentile(x, (5, 95))
    rows = x.mean(axis=1)
    p1, p90 = np.percentile(rows, (1, 90))
    writer.writerow((phase, index, round(blocks.mean(), 3), round(100*(p95-p5)/(p95+p5), 3),
                     round(100*(1-p1/p90), 3), round(100*x.std()/x.mean(), 3)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    args = p.parse_args()
    out = csv.writer(sys.stdout, lineterminator='\n')
    out.writerow(('phase', 'frame', 'mean_dn', 'flat_block_contrast_pct', 'flat_row_p01_dip_pct', 'flat_cv_pct'))
    for ref, phases in (('d13_matchreturn', ('e01_match', 'e03_matchreturn')),
                        ('d02_stockLong', ('e02_ref',)), ('d01_activeLong', ('e04_activeEven',))):
        long = np.array(list(frames(args.directory, ref, 25000)))
        # Check long-frame repeatability against the other frames, not itself.
        for i, frame in enumerate(long):
            measure(out, ref, i+1, frame, np.median(np.delete(long, i, axis=0), axis=0))
        flat = np.median(long, axis=0)
        for ph in phases:
            for i, frame in enumerate(frames(args.directory, ph, 4000), 1):
                measure(out, ph, i, frame, flat)


if __name__ == '__main__':
    main()
