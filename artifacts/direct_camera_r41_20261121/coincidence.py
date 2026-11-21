#!/usr/bin/env python3
"""R41 within-frame CFA notch coincidence: python coincidence.py FRAMES channels.csv > mixed.csv

The G1 row from measure.py fixes the event for this DNG only. On native GBRG,
G1 and B sample even RAW rows; R at that same physical y is interpolated from
the two bracketing odd rows. R36 characterize uses a separate local plateau
for each three-cell-smoothed profile. Its half-depth center is an alignment
diagnostic, never the amplitude sample. Blank centers mean no bounded crossing.
B is secondary. These are overlapping camera passbands, not isolated panel
primaries; white, whiteRet and yellow are separate shutter phases.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r36_20261120.channels import characterize
from direct_camera_r41_20261121.measure import ROI, SITES, decode_dng_bytes, extract_metadata, inputs


PHASE_NS = {f'b{ns}_{scene}': ns for ns in (125000, 200000, 312500, 500000)
            for scene in ('white', 'yellow', 'whiteRet')}


def anchors(stream):
    reader = csv.DictReader(stream, strict=True)
    fields = reader.fieldnames or []
    required = {'phase', 'frame_n', 'site', 'gate', 'mean_dn', 'notch_center_raw_y', 'row_notch_pct'}
    if len(fields) != len(set(fields)) or not required.issubset(fields):
        raise ValueError('invalid channels.csv header')
    refs = {}
    for row in reader:
        if row['phase'] not in PHASE_NS or row['site'] != 'G1':
            continue
        try:
            key = row['phase'], int(row['frame_n'])
            y = int(row['notch_center_raw_y']) if row['notch_center_raw_y'] else None
            depth = float(row['row_notch_pct']) if row['row_notch_pct'] else None
            mean = float(row['mean_dn'])
            if None in row or None in row.values() or key[1] < 1 or key in refs or not np.isfinite(mean):
                raise ValueError
            if (y is None) != (depth is None):
                raise ValueError
            if y is not None and (row['gate'] != 'ok' or y % 2 or not np.isfinite(depth) or depth <= 0
                                  or not 2*(ROI[0]+41) <= y <= 2*(ROI[1]-42)):
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError(f'invalid or duplicate G1 reference on channels.csv line {reader.line_num}') from None
        refs[key] = row['gate'], mean, y, depth
    return refs


def measure(phase, n, path, ref):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['orientation'], m['width'], m['height'], m['cfa_pattern_2x2'],
         m['focal_length_mm'], m['iso']) != ('Nothing', 'A001', 1, 4080, 3072, [1, 2, 0, 1], 5.56, 6400)
            or not abs(1000*m['exposure_us'] - PHASE_NS[phase]) <= 1):
        raise ValueError('wrong camera geometry, ISO or exposure')

    ref_gate, ref_mean, event, ref_depth = ref
    y0, y1, x0, x1 = ROI
    results = {}
    for site, i in SITES:
        if site == 'G2':
            continue
        dy, dx = divmod(i, 2)
        plane = raw[2*y0+dy:2*y1:2, 2*x0+dx:2*x1:2]
        signal = plane.mean(axis=1) - m['black_levels'][i]
        mean = signal.mean()
        clip, floor = np.count_nonzero(plane >= m['white_level']), np.count_nonzero(plane == 0)
        gate = 'clipped' if clip else 'storage_floor' if floor else 'below_20dn' if mean < 20 else 'ok'
        status = gate if gate != 'ok' else 'no_g1_anchor' if event is None else 'ok'
        plateau = at = depth = center = None
        if status == 'ok':
            rows = 2*np.arange(y0+1, y1-1) + dy
            profile = np.convolve(signal, np.ones(3)/3, 'valid')
            # At the first admissible even G1 row the nearest lower R row can
            # lack a complete R36 window. Do not shift the anchor to fit it.
            try:
                plateau, at, depth, _, center = characterize(rows, profile, event)
            except ValueError:  # incomplete window or nonpositive local plateau
                status = 'no_local_plateau'
        if site == 'G1' and (gate != ref_gate or not np.isclose(mean, ref_mean, rtol=1e-8, atol=1e-8)
                             or (event is not None and (depth is None or abs(depth-ref_depth) > 1e-6))):
            raise ValueError('G1 gate, mean or fixed-row depth disagrees with channels.csv')
        results[site] = dict(phase=phase, frame_n=n, exposure_us=m['exposure_us'], site=site,
                             fixed_g1_raw_y=event, mean_dn=mean, clip_n=clip, floor_n=floor, gate=gate,
                             status=status, local_plateau_dn=plateau, dn_at_g1=at, depth_at_g1_pct=depth,
                             half_center_raw_y=center)

    g1_center = results['G1']['half_center_raw_y']
    for site in ('G1', 'R', 'B'):
        row = results[site]
        center = row['half_center_raw_y']
        yield dict(**row, half_center_minus_g1_rows=(center - g1_center
                   if center is not None and g1_center is not None else None))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    ap.add_argument('channels_csv', type=Path, metavar='channels.csv')
    args = ap.parse_args()
    try:
        paths = {k: p for k, p in inputs(args.frames).items() if k[0] in PHASE_NS}
        with args.channels_csv.open(newline='') as stream:
            refs = anchors(stream)
        if not paths or paths.keys() != refs.keys():
            raise ValueError('selected DNGs and G1 references must match one-to-one')
        rows = []
        for phase, n in sorted(paths):
            try:
                rows.extend(measure(phase, n, paths[phase, n], refs[phase, n]))
            except ValueError as exc:
                raise ValueError(f'{phase}/{n}: {exc}') from None
    except OSError as exc:
        ap.error(exc.strerror)  # never print private paths
    except (csv.Error, ValueError) as exc:
        ap.error(str(exc))

    missing = PHASE_NS.keys() - {ph for ph, n in paths}
    if missing:
        print('Partial R41 inventory; missing: ' + ', '.join(sorted(missing)), file=sys.stderr)
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
