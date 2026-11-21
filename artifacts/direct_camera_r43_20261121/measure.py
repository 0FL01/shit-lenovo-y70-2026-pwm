#!/usr/bin/env python3
"""R43: python3 -B measure.py FRAMES > frames.csv (one row per phase__N.dng).

Group and scene are acquisition labels, not evidence of panel state. G1 is
primary; R42's halves and other CFA sites use the same physical RAW row. DN
are signed above the site's tagged black. Percentiles have no flat correction.
shutter_band distinguishes the 125..500 us series from longer integrations;
the actual cause of an unqualified event is not inferred from the exposure.
dl_us = exposure_us * depth_pct / 100: equivalent missing plateau light during
integration, not off-time. Compare across shutters; a smooth long exposure or
a blank event is not evidence of DC. The candidate's local noise threshold is
also reported: the R42 shoulder gate, not a bound on undetected modulation.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.measure import ROI, SITES, fixed_event, inputs, read_sites, row_notch, sample


EXPOSURES = {'125': 125, '200': 200, '312': 312.5, '500': 500, '1250': 1250,
             '4000': 4000, '6667': 6666.667, '25000': 25000}


def phase_info(phase):
    *labels, token = phase.split('_')
    if (len(labels) < 2 or token not in EXPOSURES or
            not all(re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', label) for label in labels)):
        raise ValueError('expected GROUP_SCENE_EXPOSURE, e.g. day_sdrRet_312')
    return labels[0], '_'.join(labels[1:]), EXPOSURES[token]


def local_noise_gate(green, event):
    """R42 fixed_event's G1 amplitude threshold, even if the dip fails its gates."""
    if event is None:
        return None, None
    k = (event // 2) - ROI[0] - 1  # center index after valid 3-cell smoothing
    p = np.convolve(green.mean(axis=1), np.ones(3)/3, 'valid')
    window = p[k-40:k+41]
    shoulders = np.r_[window[:25], window[-25:]]
    plateau = np.median(window)
    threshold = max(1., 5 * 1.4826 * np.median(abs(shoulders - np.median(shoulders))))
    return threshold, 100 * threshold / plateau if plateau >= 20 else None


def measure(phase, n, path):
    group, scene, exposure = phase_info(phase)
    if n < 1:
        raise ValueError('frame index must be positive')
    m, planes = read_sites(path, exposure)  # verifies tags including ISO, CFA, exposure
    control = 'black' in (group, *scene.split('_'))
    y0, y1, x0, x1 = ROI
    black, white = m['black_levels'], m['white_level']
    green, stats = sample(planes['G1'], black[0], white, control)
    usable = stats['gate'] == 'ok'
    blocks = green.reshape((y1-y0)//5, 5, (x1-x0)//5, 5).mean(axis=(1, 3))
    p5, p95 = np.percentile(blocks, (5, 95))
    p1, p90 = np.percentile(blocks.mean(axis=1), (1, 90))
    event = row_notch(green, y0, usable)['notch_center_raw_y']
    noise_dn, noise_pct = local_noise_gate(green, event)
    row = dict(phase=phase, group=group, scene=scene, frame_n=n, exposure_us=m['exposure_us'],
               shutter_band='short' if exposure <= 500 else 'long_integration',
               iso=m['iso'], width=m['width'], height=m['height'], orientation=m['orientation'],
               focal_mm=m['focal_length_mm'], cfa='GBRG', y0=y0, y1=y1, x0=x0, x1=x1,
               black_dn=black[0], white_dn=white, **stats, block_p05_dn=p5, block_p95_dn=p95,
               row_p01_dn=p1, row_p90_dn=p90,
               block_contrast_pct=100*(p95-p5)/(p95+p5) if usable and p95+p5 > 0 else None,
               row_p01_dip_pct=100*(1-p1/p90) if usable and p90 > 0 else None,
               candidate_raw_y=event, local_noise_gate_dn=noise_dn, local_noise_gate_pct=noise_pct)

    status, metrics = stats['gate'] if not usable else 'no_candidate', {}
    if event is not None:
        status, metrics = fixed_event(green, 0, event)

    def check(prefix, stored, i):
        signal, counts = sample(stored, black[i], white, control)
        gate, values = counts['gate'], {}
        if gate == 'ok':
            gate, values = fixed_event(signal, i//2, event) if status == 'ok' else ('no_g1_event', {})
        counts.update(status=gate, depth_pct=values.get('depth_pct'))
        row.update({prefix+'_'+k: v for k, v in counts.items()})
        return gate

    mid = green.shape[1]//2
    left = check('left', planes['G1'][:, :mid], 0)
    right = check('right', planes['G1'][:, mid:], 0)
    if status == 'ok' and (left, right) != ('ok', 'ok'):
        status = 'half_check_failed'
    for site, i in SITES:
        if site != 'G1':
            check(site.lower(), planes[site], i)
    row.update(event_status=status, fixed_g1_raw_y=event if status == 'ok' else None)
    for key in ('local_plateau_dn', 'min_dn', 'depth_pct', 'michelson_pct', 'fwhm_raw_rows'):
        row[key] = metrics[key] if status == 'ok' else None
    row['drop_dn'] = row['local_plateau_dn'] - row['min_dn'] if status == 'ok' else None
    row['dl_us'] = row['exposure_us'] * row['depth_pct'] / 100 if status == 'ok' else None
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    rows = []
    try:
        for (phase, n), path in sorted(inputs(args.frames).items()):
            try:
                rows.append(measure(phase, n, path))
            except ValueError as exc:
                raise ValueError(f'{phase}/{n}: {exc}') from None
    except OSError as exc:
        ap.error(exc.strerror)
    except ValueError as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
