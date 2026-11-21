#!/usr/bin/env python3
"""R43 evening: python3 -B evening.py FRAMES [--windows windows.csv] > evening.csv

G1 camera DN above tagged black, in the fixed R42 ROI. Match the median of
25 ms frame means (gross and minus the mode's black) to even_sdr within ±5%,
including the SDR return. This is a camera match, not photometry. A failed
match does not suppress the observed within-scene metrics. Each lit frame is
divided by its own scene's median flat; long frames exclude themselves. The
second set of metrics subtracts the black block map at each exposure BEFORE
division. Without windows.csv, scene/BL associations are acquisition labels.
"""
import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.evening import FLOOR, metrics
from direct_camera_r43_20261121.measure import EXPOSURES, ROI, read_sites


BLACK = {'even_sdr': 'black_sdr', 'even_hdr': 'black_hdr', 'even_sdrRet': 'black_sdr'}
TIMES = ('25000', '4000', '6667')
LONG = TIMES[0]
KEYS = [(group, t) for group in (*BLACK, 'black_sdr', 'black_hdr') for t in TIMES]


def load(frames):
    data, seen = {}, set()
    for group, t in KEYS:
        phase = f'{group}_{t}'
        files = {}
        for p in frames.glob(phase + '__*'):
            match = re.fullmatch(r'[1-9][0-9]*\.dng', p.name.split('__', 1)[1])
            if not match:
                raise ValueError(f'{p.name}: malformed or incomplete frame')
            files[int(p.stem.split('__')[1])] = p
        if not files or sorted(files) != list(range(1, len(files)+1)):
            raise ValueError(f'{phase}: need contiguous DNGs starting at 1')
        if group in BLACK and t == LONG and len(files) < 3:
            raise ValueError(f'{phase}: need at least three independent flats')
        samples = []
        for p in (files[n] for n in sorted(files)):
            try:
                m, sites = read_sites(p, EXPOSURES[t])  # checks actual shutter, ISO, lens, CFA and geometry
            except ValueError as exc:
                raise ValueError(f'{p.name}: {exc}') from None
            g = sites['G1']
            if m['white_level'] != 1023 or not np.isfinite(m['black_levels'][0]):
                raise ValueError(f'{p.name}: unexpected DN scale')
            digest = blake2b(g.tobytes(), digest_size=16).digest()
            if digest in seen:
                raise ValueError(f'{p.name}: reused G1 samples, not an independent frame')
            seen.add(digest)
            h, w = g.shape
            blocks = g.reshape(h//5, 5, w//5, 5).mean(axis=(1, 3)) - m['black_levels'][0]
            samples.append((blocks, g.min() == 0 or g.max() >= m['white_level'], m['exposure_us']))
        data[group, t] = samples
    return data


def verify_windows(path, data):
    expected = {f'{g}_{t}': (g, t) for g, t in KEYS}
    windows = {}
    with path.open(newline='') as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if not fields or len(set(fields)) != len(fields):
            raise ValueError('windows.csv: missing or repeated column names')
        for w in reader:
            phase = w['phase']
            if phase not in expected:
                continue
            group, t = expected[phase]
            mode = 'hdr' if group.endswith('_hdr') else 'sdr'
            records = data[group, t]
            if (None in w or None in w.values() or phase in windows
                or w['group'] != group.split('_')[0] or w['scene'] != mode
                or (w['hwc_dynamic_range'], w['sdm_dynamic_range']) != (mode.upper(), mode.upper())
                or int(w['frames']) != len(records) or int(w['iso']) != 6400
                or tuple(int(w[k]) for k in ('roi_y0','roi_y1','roi_x0','roi_x1')) != ROI
                or int(w['sysfs_bl']) <= 0 or int(w['wake_epoch']) <= 0
                or not (int(w['hwc_id']) == int(w['sdm_config']) >= 0
                        and float(w['sf_refresh_hz']) == float(w['sdm_fps']) > 0)
                or any(abs(us*1000-int(w['exposure_ns'])) > 1 for _, _, us in records)):
                raise ValueError(f'{phase}: window does not match scene or original frames')
            windows[phase] = w
    if windows.keys() != expected.keys():
        raise ValueError(f'missing windows: {sorted(expected.keys() - windows.keys())}')
    if len({w['wake_epoch'] for w in windows.values()}) != 1:
        raise ValueError('evening windows span different session wakes')
    for t in TIMES:
        bracket = [f'{g}_{t}' for g in BLACK]
        if [p for p in windows if p in bracket] != bracket:
            raise ValueError(f'{t}: receipt order does not establish SDR -> HDR -> SDR return')
    for mode in ('hdr', 'sdr'):
        # Includes the lit scene, its black at all three shutters, and the SDR return.
        states = {tuple(w[k] for k in ('sysfs_bl', 'hwc_id', 'sf_refresh_hz', 'sdm_config', 'sdm_fps'))
                  for w in windows.values() if w['scene'] == mode}
        if len(states) != 1:
            raise ValueError(f'{mode}: BL or refresh/config differs between scene, flat, black or return')
    return windows


def rows(data, windows=None):
    maps = {k: np.median([b for b, _, _ in rec], axis=0) for k, rec in data.items()}
    rails = {k: any(r for _, r, _ in rec) for k, rec in data.items()}
    means = {g: [b.mean() for b, _, _ in data[g, LONG]] for g, t in KEYS if t == LONG}
    gross = {g: np.median(v) for g, v in means.items()}
    net = {g: gross[g]-gross[bg] for g, bg in BLACK.items()}
    gross_ok = {g: not rails[g, LONG] and min(means[g]) >= FLOOR for g in BLACK}
    net_ok = {g: gross_ok[g] and not rails[bg, LONG] and min(means[g])-gross[bg] >= FLOOR
              for g, bg in BLACK.items()}

    def delta(g, levels, valid):
        if valid[g] and valid['even_sdr']:
            return 100 * (levels[g] - levels['even_sdr']) / levels['even_sdr']

    dg = {g: delta(g, gross, gross_ok) for g in BLACK}
    dn = {g: delta(g, net, net_ok) for g in BLACK}
    match = {g: ('invalid_25ms_signal' if None in (dg[g], dn[g]) else
                 'outside_5pct' if max(abs(dg[g]), abs(dn[g])) > 5 else 'ok') for g in BLACK}
    # Comparison gate is for the whole SDR -> HDR -> SDR bracket, not a rail/noise
    # gate for a particular exposure (those are in gross_gate and map_net_gate).
    failures = [f'{g}:{s}' for g, s in match.items() if s != 'ok']
    comparison = ';'.join(failures) or ('ok' if windows is not None else 'windows_unverified')

    for g, t in KEYS:
        phase, bg = f'{g}_{t}', BLACK.get(g)
        long = data[g, LONG]
        for j, (b, rail, us) in enumerate(data[g, t]):
            loo = t == LONG
            gate = net_gate = 'black_control'
            dip = contrast = net_mean = net_dip = net_contrast = None
            nrefs = 0
            if bg:
                refs = long[:j]+long[j+1:] if loo else long
                nrefs = len(refs)
                flat = np.median([x for x, _, _ in refs], axis=0) if loo else maps[g, LONG]
                initial = 'frame_or_flat_rail' if rail or any(r for _, r, _ in refs) else 'ok'
                gate, dip, contrast = metrics(b, flat, initial)
                sub = b - maps[bg, t]
                net_mean = sub.mean()
                net_gate, net_dip, net_contrast = metrics(sub, flat - maps[bg, LONG],
                    'black_control_rail' if rails[bg, t] or rails[bg, LONG] else initial)
            yield dict(phase=phase, group=g, frame_n=j+1, site='G1', exposure_us=us,
                       role=('flat_loo' if loo else 'short') if bg else 'black_control',
                       flat_n_used=nrefs, matched_black=f'{bg}_{t}' if bg else None,
                       sysfs_bl=windows[phase]['sysfs_bl'] if windows is not None else None,
                       windows_gate='verified' if windows is not None else 'not_checked',
                       mean_dn=b.mean(), frame_rail=int(rail), flat_gross_median_dn=gross[g],
                       flat_black_median_dn=gross[bg] if bg else None, flat_net_dn=net.get(g),
                       flat_gross_vs_sdr_pct=dg.get(g), flat_net_vs_sdr_pct=dn.get(g),
                       match_gate=match.get(g), comparison_gate=comparison,
                       gross_gate=gate, row_dip_pct=dip, block_contrast_pct=contrast,
                       map_net_mean_dn=net_mean, map_net_gate=net_gate,
                       map_net_row_dip_pct=net_dip, map_net_block_contrast_pct=net_contrast)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    ap.add_argument('--windows', type=Path, help='checked windows.csv from R43 windows.py')
    ap.add_argument('--selected', choices=[*BLACK, 'HDR'], help='output only this lit group (HDR = even_hdr); still validate the full bracket')
    args = ap.parse_args()
    try:
        data = load(args.frames)
        windows = verify_windows(args.windows, data) if args.windows else None
        selected = 'even_hdr' if args.selected == 'HDR' else args.selected
        result = [r for r in rows(data, windows) if selected is None or r['group'] == selected]
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=result[0], lineterminator='\n')
    writer.writeheader()
    for row in result:
        writer.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k,v in row.items()})


if __name__ == '__main__':
    main()
