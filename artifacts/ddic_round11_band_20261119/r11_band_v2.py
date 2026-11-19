#!/usr/bin/env python3
"""Round 11 offline v2: chop frequency/depth estimates from existing DNGs.

Two camera-only estimators, assumptions stated explicitly:

(A) sinc-consistency of the dip metric: if the DC-landed residual chop is a
    periodic brightness modulation of frequency f, the fraction of ROI blocks
    below 0.65x (lt065) and the [1,0] 2D-peak amplitude should fall with
    |sinc(f*T_exp)| as the exposure averages over chop cycles. We fit the
    R10 sweep points (2 frames each) against candidate frequencies.

(B) smoothed band geometry on dip frames: 21-row Hann smoothing of the
    green row profile inside the analyzer ROI, dark-band runs and depths.
    Absolute row->time conversion uses the labeled assumption
    row_pitch ~= frameDuration/rows (33.33ms/2448 ~= 13.6 us/row).

No device I/O; inputs are existing DNGs from the private evidence dir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

R113 = Path(__file__).resolve().parent.parent / 'night_r113_camera_notch'
if str(R113) not in sys.path:
    sys.path.insert(0, str(R113))
import dng_qualify  # noqa: E402

COL_LO, COL_HI = 1860, 2020
ROW_LO, ROW_HI = 90, 270
ROW_PITCH_US = 33.333e3 / 2448.0   # assumption: readout ~= frame interval


def green_profiles(path: Path):
    raw, tags = dng_qualify.decode_dng_bytes(path.read_bytes())
    meta = dng_qualify.extract_metadata(tags)
    cfa = meta['cfa_pattern_2x2']
    blacks = meta['black_levels']
    planes = []
    for idx in [i for i, c in enumerate(cfa) if c == 1]:
        dy, dx = divmod(idx, 2)
        plane = raw[dy::2, COL_LO:COL_HI].astype(np.float64) - float(blacks[idx])
        planes.append(plane.mean(axis=1))
    prof = np.empty(2 * len(planes[0]))
    prof[0::2] = planes[0]
    prof[1::2] = planes[1] if len(planes) > 1 else planes[0]
    return prof, float(np.mean([p.mean() for p in planes]))


def smooth(x: np.ndarray, w: int = 21) -> np.ndarray:
    win = np.hanning(w)
    win /= win.sum()
    return np.convolve(x, win, mode='same')


def bands(prof, rel=0.75, min_run=8):
    seg = smooth(prof[ROW_LO:ROW_HI])
    edge = len(seg) // 8
    core = seg[edge:-edge]                      # drop convolution edge artifacts
    med = np.median(core)
    dark = core < rel * med
    runs, s = [], None
    for i, v in enumerate(dark):
        if v and s is None:
            s = i
        elif not v and s is not None:
            runs.append((s, i))
            s = None
    if s is not None:
        runs.append((s, len(dark)))
    runs = [(a, b) for a, b in runs if b - a >= min_run]
    return runs, core, med


def sinc_val(f, t_us):
    x = np.pi * f * t_us * 1e-6
    return abs(np.sin(x) / x) if x != 0 else 1.0


def main(ev_dir: str, out_json: str) -> int:
    ev = Path(ev_dir)

    sweep = [  # (T_us, files) from the R10 v3 sweep at DBV 460
        (125.0, ['IMG_20260502_144040387.DNG', 'IMG_20260502_144044314.DNG']),
        (500.0, ['IMG_20260502_144105165.DNG', 'IMG_20260502_144109079.DNG']),
        (625.0, ['IMG_20260502_144127654.DNG', 'IMG_20260502_144131564.DNG']),
        (800.0, ['IMG_20260502_144150574.DNG', 'IMG_20260502_144154498.DNG']),
        (1562.5, ['IMG_20260502_144238370.DNG', 'IMG_20260502_144242277.DNG']),
        (12500.0, ['IMG_20260502_144315618.DNG', 'IMG_20260502_144319557.DNG']),
    ]
    # per-frame block-dip fraction from the binned 5x5 analysis (analyzer output)
    lt065 = {
        (125.0): [0.3993, 0.4549], (500.0): [0.3056, 0.3160],
        (625.0): [0.4062, 0.2951], (800.0): [0.4097, 0.2674],
        (1562.5): [0.1389, 0.1319], (12500.0): [0.0, 0.0],
    }
    freqs = [360, 480, 600, 640, 720, 840, 960, 1200, 1440, 2160]
    print('== (A) sinc consistency of lt065 vs candidate chop frequencies ==')
    fits = {}
    for f in freqs:
        errs = []
        for t, vals in lt065.items():
            s = sinc_val(f, t)
            for v in vals:
                # relative error: dips should scale ~ (lt065 - floor)/ (s * max_lt)
                errs.append(abs(v - 0.42 * s) / 0.42)
        rmse = float(np.sqrt(np.mean(np.square(errs))))
        fits[f] = rmse
        print(f'  f={f:5d} Hz  RMSE(lt065 vs 0.42*|sinc|) = {rmse:.4f}')
    best = min(fits, key=fits.get)
    print(f'  -> best candidate: {best} Hz (RMSE {fits[best]:.4f})')

    print('== (B) smoothed band geometry on dip frames (row_pitch='
          f'{ROW_PITCH_US:.2f} us/row assumption) ==')
    out = {'sinc_fits_rmse': {str(k): round(v, 4) for k, v in fits.items()},
           'sinc_best_hz': best, 'row_pitch_us': round(ROW_PITCH_US, 3),
           'frames': {}}
    for label, fn in [
        ('dc_460_dark625', 'IMG_20260502_144127654.DNG'),
        ('dc_460_bright625', 'IMG_20260502_144131564.DNG'),
        ('dc_460_dark800', 'IMG_20260502_144150574.DNG'),
        ('dc_460_floor625_1', 'IMG_20260502_142038399.DNG'),
        ('pwm_460_base_1', 'IMG_20260502_142005471.DNG'),
    ]:
        prof, mean = green_profiles(ev / fn)
        runs, core, med = bands(prof)
        heights = [round(float((b - a) * ROW_PITCH_US), 1) for a, b in runs]
        depths = [round(float(np.min(core[a:b]) / med), 3) for a, b in runs]
        out['frames'][label] = {
            'file': fn, 'mean_dn': round(mean, 4),
            'dark_runs': [[int(a), int(b)] for a, b in runs],
            'run_durations_us': heights,
            'run_depth_min_rel': depths,
        }
        print(f'  {label} ({fn}) mean={mean:.3f} bands={len(runs)} '
              f'durations_us={heights[:6]} depths={depths[:6]}')
    Path(out_json).write_text(json.dumps(out, indent=1))
    print('wrote', out_json)
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: r11_band_v2.py EVIDENCE_DIR OUT_JSON')
    sys.exit(main(sys.argv[1], sys.argv[2]))
