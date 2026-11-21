"""Compare the same sensor strips across releases; hold out alternate G1 columns."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.measure import EXPOSURES, ROI, read_sites, sample


def score(select, validate):
    hi, lo = select.argmax(axis=0), select.argmin(axis=0)
    y = np.arange(select.shape[1])
    light, dark = validate[hi, y], validate[lo, y]
    good = (select[hi, y] >= 20) & (light >= 20)
    delta = np.full(light.shape, np.nan)
    delta[good] = 100 * (1 - dark[good] / light[good])
    return delta


def measure(frames, w):
    phase = w['phase']
    *_, tok = phase.split('_')
    halves = []
    seen = set()
    for i in range(1, int(w['frames']) + 1):
        m, planes = read_sites(frames/f'{phase}__{i}.dng', EXPOSURES[tok])
        data = planes['G1'].tobytes()
        if data in seen:
            raise ValueError(f'{phase}: duplicate G1 samples')
        seen.add(data)
        g, stats = sample(planes['G1'], m['black_levels'][0], m['white_level'], False)
        if stats['gate'] != 'ok':
            return dict(phase=phase, status=stats['gate'])
        halves.append([part.reshape((ROI[1]-ROI[0])//5, 5, -1).mean(axis=(1, 2))
                       for part in (g[:, ::2], g[:, 1::2])])
    if len(halves) != 5:
        raise ValueError(f'{phase}: require five independent releases')
    a, b = np.array(halves).transpose(1, 0, 2)
    both = np.minimum(score(a, b), score(b, a))
    v = both[np.isfinite(both)]
    out = dict(phase=phase, status='ok' if v.size else 'no_bright_reference',
               raw_rows_per_strip=10, total=both.size, qualified=v.size)
    if v.size:
        out.update(median_pct=np.median(v), p90_pct=np.percentile(v, 90), ge50=int(sum(v >= 50)))
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path); ap.add_argument('windows', type=Path)
    args=ap.parse_args()
    with args.windows.open() as f:
        rows = [measure(args.frames, w) for w in csv.DictReader(f) if w['group']=='day']
    out=csv.DictWriter(sys.stdout, fieldnames='phase status raw_rows_per_strip total qualified median_pct p90_pct ge50'.split(), lineterminator='\n')
    out.writeheader()
    for r in rows:
        out.writerow({k:format(v,'.7g') if isinstance(v,float) else v for k,v in r.items()})


if __name__ == '__main__':
    main()
