#!/usr/bin/env python3
"""R42 evening: python3 -B evening.py FRAMES > evening.csv

G1, signed DN above the tagged BlackLevel. Acquisition labels assume BL 512;
the DNG verifies camera settings, not the screen content or panel state.
Flat matching columns (25 ms rows only) use medians of whole-ROI frame means.
Ratios are multiples, with equality at 1. The additive net estimate subtracts
the matched black-center scene; it assumes the surround contribution is the
same with the center white or black. It is not a measurement of emitted light
in isolation.

Each 4 ms frame uses its scene's median 25 ms block map. A 25 ms frame uses
only the other flats of its scene. As a sensitivity check, subtract the median
matched black map at *each map's own exposure* before taking the quotient.
Unqualified comparisons are blank, never zero. Row dip and block contrast are
camera-image percentages; the black controls themselves retain DN diagnostics.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

ARTIFACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACTS))
from direct_camera_r41_20261121.light import extract_metadata, read_dng

ROI = (630, 1250, 754, 799)  # native Bayer cells: y0:y1, x0:x1
if Path(__file__).with_name('measure.py').is_file():
    from direct_camera_r42_20261121.measure import ROI as DAY_ROI
    if tuple(DAY_ROI) != ROI:
        raise ValueError('R42 evening and day ROI disagree; requalify the common ROI')

BLACK = dict(full='inverse', core='dark', loaded='ring', coreRet='dark', fullRet='inverse')
SCENES = (*BLACK, 'ring', 'dark', 'inverse')
US = dict(flat=25000, short=4000)
FLOOR = 20


def read_blocks(path, end):
    raw, tags = read_dng(path)
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['width'], m['height'], m['orientation'],
         m['cfa_pattern_2x2'], m['focal_length_mm'], tags.get(33437), m['iso'], m['white_level']) !=
            ('Nothing', 'A001', 4080, 3072, 1, [1, 2, 0, 1], 5.56, [1.87], 6400, 1023)
            or raw.shape != (3072, 4080) or not np.isclose(m['exposure_us'], US[end], rtol=0, atol=.001)):
        raise ValueError(f'{path.name}: unexpected A001 geometry, optics, ISO, DN scale or exposure')
    y0, y1, x0, x1 = ROI
    g1 = raw[2*y0:2*y1:2, 2*x0:2*x1:2]  # first site in GBRG
    rail = bool(g1.min() == 0 or g1.max() >= m['white_level'])
    blocks = g1.reshape((y1-y0)//5, 5, (x1-x0)//5, 5).mean(axis=(1, 3)) - m['black_levels'][0]
    return blocks, rail


def load(frames):
    groups = {(s, e): {} for s in SCENES for e in US}
    seen = set()
    for p in frames.glob('e_*.dng'):
        match = re.fullmatch(r'e_(\w+)_(flat|short)__(\d+)\.dng', p.name)
        if not match or match[1] not in SCENES:
            raise ValueError(f'unrecognized evening frame: {p.name}')
        group = groups[match[1], match[2]]
        n = int(match[3]); st = p.stat(); identity = (st.st_dev, st.st_ino)
        if n in group or identity in seen:
            raise ValueError(f'duplicate evening frame: {p.name}')
        group[n] = p
        seen.add(identity)
    data = {}
    for (scene, end), group in groups.items():
        if not group or sorted(group) != list(range(1, len(group)+1)):
            raise ValueError(f'e_{scene}_{end}: need contiguous frames from 1')
        if scene in BLACK and end == 'flat' and len(group) < 3:
            raise ValueError(f'e_{scene}_flat: need at least three independent flats')
        data[scene, end] = [read_blocks(group[i], end) for i in sorted(group)]
    return data


def metrics(blocks, flat, gate):
    if gate == 'ok' and blocks.mean() < FLOOR:
        gate = 'below_20dn'
    if gate == 'ok' and flat.min() <= FLOOR:
        gate = 'flat_block_at_or_below_20dn'
    if gate != 'ok':
        return gate, None, None
    q = blocks / flat
    p1, p90 = np.percentile(q.mean(axis=1), (1, 90))
    p5, p95 = np.percentile(q, (5, 95))
    if p90 <= 0 or p95 + p5 <= 0:
        return 'invalid_denominator', None, None
    return 'ok', 100*(1-p1/p90), 100*(p95-p5)/(p95+p5)


def rows(data):
    def arrays(group):
        return [b for b, _ in group]

    # Level matching and spatial correction are distinct estimators:
    # median of frame means for matching, coordinatewise median for maps.
    gross = {}; good = {}; net = {}; net_good = {}; black_maps = {}
    for s in SCENES:
        long = data[s, 'flat']
        means = [b.mean() for b, _ in long]
        gross[s] = np.median(means)
        good[s] = min(means) >= FLOOR and not any(rail for _, rail in long)
        if s not in BLACK:
            for end in US:
                group = data[s, end]
                black_maps[s, end] = np.median(arrays(group), axis=0), any(rail for _, rail in group)
    for s, bg in BLACK.items():
        net[s] = gross[s] - gross[bg]
        net_good[s] = (good[s] and not black_maps[bg, 'flat'][1] and
                       all(b.mean()-gross[bg] >= FLOOR for b, _ in data[s, 'flat']))

    for s in SCENES:
        bg = BLACK.get(s)
        long = data[s, 'flat']
        for end in US:
            loo = end == 'flat'
            for j, (blocks, rail) in enumerate(data[s, end]):
                refs = long[:j] + long[j+1:] if loo else long
                flat = np.median(arrays(refs), axis=0) if refs else None
                gate = 'ok'
                if rail or any(r for _, r in refs):
                    gate = 'frame_or_flat_rail'
                elif len(long) < 3:
                    gate = 'too_few_flats'
                status, dip, contrast = metrics(blocks, flat, gate)
                net_mean = net_dip = net_contrast = None
                net_status = 'black_control'
                if bg:
                    dark, dark_rail = black_maps[bg, end]
                    dark_flat, flat_rail = black_maps[bg, 'flat']
                    net_blocks = blocks - dark
                    net_mean = net_blocks.mean()
                    net_status, net_dip, net_contrast = metrics(net_blocks, flat - dark_flat,
                        'black_control_rail' if dark_rail or flat_rail else status)
                yield dict(phase=f'e_{s}_{end}', frame_n=j+1, site='G1', exposure_us=US[end],
                    role='flat_loo' if loo else 'short', flat_n_used=len(refs), matched_black=bg,
                    mean_dn=blocks.mean(), flat_gross_median_dn=gross[s] if loo else None,
                    flat_gross_ratio_to_full=gross[s]/gross['full'] if loo and good[s] and good['full'] else None,
                    flat_black_median_dn=gross[bg] if loo and bg else None,
                    flat_net_additive_dn=net[s] if loo and bg else None,
                    flat_net_additive_ratio_to_core=net[s]/net['core'] if loo and bg and net_good[s] and net_good['core'] else None,
                    flat_net_additive_ratio_to_full=net[s]/net['full'] if loo and bg and net_good[s] and net_good['full'] else None,
                    gross_gate=status, row_dip_pct=dip, block_contrast_pct=contrast,
                    map_net_mean_dn=net_mean, map_net_gate=net_status, map_net_row_dip_pct=net_dip,
                    map_net_block_contrast_pct=net_contrast)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    try:
        result = list(rows(load(args.frames)))
    except OSError as exc:
        ap.error(exc.strerror)
    except ValueError as exc:
        ap.error(str(exc))
    w = csv.DictWriter(sys.stdout, fieldnames=result[0], lineterminator='\n')
    w.writeheader()
    for row in result:
        w.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k,v in row.items()})


if __name__ == '__main__':
    main()
