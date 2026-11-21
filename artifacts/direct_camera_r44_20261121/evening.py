#!/usr/bin/env python3
"""R44: python evening.py FRAMES --windows windows.csv > evening.csv

Compare actual HDR at Flicker prevention OFF -> ON -> OFF return. Match the
25 ms G1 camera level to initial OFF within ±5%, both gross (above the tagged
black) and net (minus the state's black control). This is not photometry.
Report within-state flat-corrected residuals even when the levels don't match.
Flat rows exclude themselves. Map-net residuals subtract a black block map at
each operand's own exposure before division; the return uses OFF blacks.
"""
import argparse
import csv
from hashlib import blake2b
from math import isfinite
from pathlib import Path
import re
import sys
from typing import NamedTuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.evening import FLOOR, metrics
from direct_camera_r43_20261121.measure import EXPOSURES, ROI, read_sites


BLACK = {'even_off': 'black_off', 'even_on': 'black_on', 'even_ret': 'black_off'}
BASE = 'even_off'
LONG = '25000'
TIMES = (LONG, '4000', '6667')
PHASES = {f'{g}_{t}': (g, t) for g in (*BLACK, 'black_off', 'black_on') for t in TIMES}


class Frame(NamedTuple):
    blocks: np.ndarray
    rail: bool
    us: float
    size: int


def frame_paths(frames, phase, counts):
    files = {}
    for p in frames.glob(phase + '__*'):
        m = re.fullmatch(phase + r'__([1-9][0-9]*)\.dng', p.name)
        if not m or p.is_symlink() or not p.is_file():
            raise ValueError(f'{p.name}: expected a complete original DNG')
        files[int(m[1])] = p
    if len(files) not in counts or sorted(files) != list(range(1, len(files) + 1)):
        raise ValueError(f'{phase}: expected {" or ".join(map(str, counts))} consecutive DNGs from 1')
    return [files[n] for n in sorted(files)]


def load(frames):
    data, seen = {}, set()
    for phase, (g, t) in PHASES.items():
        counts = (2,) if g not in BLACK else (3,) if t == LONG else (3, 4)
        records = []
        for p in frame_paths(frames, phase, counts):
            try:
                m, sites = read_sites(p, EXPOSURES[t])  # checks actual ISO, shutter, optics, native ROI/CFA
            except ValueError as exc:
                raise ValueError(f'{p.name}: {exc}') from None
            black, white, g1 = m['black_levels'][0], m['white_level'], sites['G1']
            if white != 1023 or not isfinite(black):
                raise ValueError(f'{p.name}: unexpected G1 DN scale')
            digest = blake2b(g1.tobytes(), digest_size=16).digest()
            if digest in seen:
                raise ValueError(f'{p.name}: reused G1 samples, not an independent frame')
            seen.add(digest)
            h, w = g1.shape
            blocks = g1.reshape(h//5, 5, w//5, 5).mean(axis=(1, 3)) - black
            rail = g1.min() == 0 or g1.max() >= white
            records.append(Frame(blocks, rail, m['exposure_us'], p.stat().st_size))
        data[g, t] = records
    return data


def verify_windows(path, data):
    windows, states = {}, set()
    with path.open(newline='') as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ValueError('windows.csv: missing or duplicate column names')
        for w in reader:
            phase = w['phase']
            if phase not in PHASES:
                continue
            if phase in windows or None in w or None in w.values():
                raise ValueError(f'{phase}: repeated or malformed window')
            g, t = PHASES[phase]
            group, stage = g.split('_')
            rec = data[g, t]
            dc = '1' if stage == 'on' else '0'
            if ((w['group'], w['dc_label'], w['session_status']) != (group, stage, 'inactive')
                    or any(w[k] != dc for k in ('panel_dc_pre', 'panel_dc_post', 'pref_pre', 'pref_post'))):
                raise ValueError(f'{phase}: expected stock {stage} with panelDC and preference {dc} at both ends')
            if ((w['scene'], w['hwc_dynamic_range'], w['sdm_dynamic_range']) != ('hdr', 'HDR', 'HDR')
                    or (w['video_dataspace'], w['sdm_tr'], w['sdm_eotf']) != ('0x11c60000', '16', 'PQ')):
                raise ValueError(f'{phase}: window does not establish HDR/PQ video and actual HDR output')
            if (int(w['frames']) != len(rec) or int(w['bytes']) != sum(r.size for r in rec)
                    or int(w['iso']) != 6400
                    or tuple(int(w[k]) for k in ('roi_y0', 'roi_y1', 'roi_x0', 'roi_x1')) != ROI
                    or any(abs(r.us*1000 - int(w['exposure_ns'])) > 1 for r in rec)):
                raise ValueError(f'{phase}: window does not match original frames')
            bl, hwc, hz = int(w['sysfs_bl']), int(w['hwc_id']), float(w['sf_refresh_hz'])
            if (bl <= 0 or hwc < 0 or int(w['sdm_config']) != hwc or not isfinite(hz)
                    or hz <= 0 or float(w['sdm_fps']) != hz):
                raise ValueError(f'{phase}: invalid BL or inconsistent HWC/refresh')
            states.add((bl, hwc, hz))
            windows[phase] = w
    if windows.keys() != PHASES.keys():
        raise ValueError(f'missing windows: {sorted(PHASES.keys() - windows.keys())}')
    wakes = {int(w['wake_epoch']) for w in windows.values()}
    if len(wakes) != 1 or min(wakes) <= 0:
        raise ValueError('evening windows do not share one wake epoch')
    if len(states) != 1:
        raise ValueError('BL or HWC/refresh differs between OFF, ON, return, flats or blacks')
    for t in TIMES:
        bracket = [f'{g}_{t}' for g in BLACK]
        if [p for p in windows if p in bracket] != bracket:
            raise ValueError(f'{t}: receipt order does not establish OFF -> ON -> OFF return')
    return windows


def rows(data, windows):
    # Level matching: median of frame means. Spatial correction: coordinatewise
    # median. They need not yield the same mean for nonuniform flats.
    maps = {k: np.median([r.blocks for r in rec], axis=0) for k, rec in data.items()}
    rails = {k: any(r.rail for r in rec) for k, rec in data.items()}
    means = {g: [r.blocks.mean() for r in rec] for (g, t), rec in data.items() if t == LONG}
    gross = {g: np.median(v) for g, v in means.items()}
    net = {g: gross[g] - gross[bg] for g, bg in BLACK.items()}
    gross_ok = {g: not rails[g, LONG] and min(means[g]) >= FLOOR for g in BLACK}
    net_ok = {g: gross_ok[g] and not rails[bg, LONG] and min(means[g])-gross[bg] >= FLOOR
              for g, bg in BLACK.items()}

    def delta(g, levels, valid):
        if valid[g] and valid[BASE]:
            return 100 * (levels[g] - levels[BASE]) / levels[BASE]

    dg = {g: delta(g, gross, gross_ok) for g in BLACK}
    dn = {g: delta(g, net, net_ok) for g in BLACK}
    match = {g: ('invalid_25ms_signal' if None in (dg[g], dn[g]) else
                 'outside_5pct' if max(abs(dg[g]), abs(dn[g])) > 5 else 'ok') for g in BLACK}
    comparison = ';'.join(f'{g}:{s}' for g, s in match.items() if s != 'ok') or 'ok'

    for phase, (g, t) in PHASES.items():
        w, bg, long = windows[phase], BLACK.get(g), data[g, LONG]
        for j, (b, rail, us, _) in enumerate(data[g, t]):
            loo = t == LONG
            nrefs = 0
            gate = net_gate = 'black_control'
            dip = contrast = net_mean = net_dip = net_contrast = None
            if bg:
                refs = long[:j] + long[j+1:] if loo else long
                nrefs = len(refs)
                flat = np.median([r.blocks for r in refs], axis=0) if loo else maps[g, LONG]
                initial = 'frame_or_flat_rail' if rail or any(r.rail for r in refs) else 'ok'
                gate, dip, contrast = metrics(b, flat, initial)
                sub = b - maps[bg, t]
                net_mean = sub.mean()
                net_gate, net_dip, net_contrast = metrics(sub, flat - maps[bg, LONG],
                    'black_control_rail' if rails[bg, t] or rails[bg, LONG] else initial)
            yield dict(phase=phase, group=g, frame_n=j+1, site='G1', exposure_us=us,
                       role=('flat_loo' if loo else 'short') if bg else 'black_control',
                       flat_n_used=nrefs, matched_black=f'{bg}_{t}' if bg else None,
                       windows_gate='verified', hwc_dynamic_range=w['hwc_dynamic_range'],
                       sdm_dynamic_range=w['sdm_dynamic_range'], panel_dc_pre=w['panel_dc_pre'],
                       panel_dc_post=w['panel_dc_post'],
                       sysfs_bl=w['sysfs_bl'], hwc_id=w['hwc_id'], sf_refresh_hz=w['sf_refresh_hz'],
                       mean_dn=b.mean(), frame_rail=int(rail), flat_gross_median_dn=gross[g],
                       flat_black_median_dn=gross[bg] if bg else None, flat_net_dn=net.get(g),
                       flat_gross_vs_off_pct=dg.get(g), flat_net_vs_off_pct=dn.get(g),
                       match_gate=match.get(g), comparison_gate=comparison, gross_gate=gate,
                       row_dip_pct=dip, block_contrast_pct=contrast, map_net_mean_dn=net_mean,
                       map_net_gate=net_gate, map_net_row_dip_pct=net_dip,
                       map_net_block_contrast_pct=net_contrast)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    ap.add_argument('--windows', type=Path, required=True, help='checked windows.csv from R44 windows.py')
    args = ap.parse_args()
    try:
        data = load(args.frames)
        result = list(rows(data, verify_windows(args.windows, data)))
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        ap.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=result[0], lineterminator='\n')
    writer.writeheader()
    for row in result:
        writer.writerow({k: format(v, '.9g') if isinstance(v, (float, np.floating)) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
