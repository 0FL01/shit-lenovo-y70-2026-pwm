#!/usr/bin/env python3
"""Round 11 offline: rolling-shutter band analysis of existing 0.6x DNGs.

Calibration: in PWM frames the ~720 Hz carrier is a known temporal period
(1389 us). Its spatial row-profile oscillation period (rows) over the frame
gives the rolling-shutter row pitch (us/row). In DC-mode dip frames, dark
band extents (rows) then convert to dark-phase durations, and band spacing
to chop period -> camera-derived chop frequency/duty estimate.

All inputs are existing DNGs from the private evidence dir; no device I/O.
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

# Full-height central column band (raw coords): avoid UI/status areas edges.
COL_LO, COL_HI = 1700, 2100
ROW_LO, ROW_HI = 40, 2440


def green_row_profile(path: Path) -> np.ndarray:
    raw, tags = dng_qualify.decode_dng_bytes(path.read_bytes())
    meta = dng_qualify.extract_metadata(tags)
    cfa = meta['cfa_pattern_2x2']
    blacks = meta['black_levels']
    gidx = [i for i, c in enumerate(cfa) if c == 1]
    # Interleave the two green CFA sites (even/odd rows) into one 2448-row profile.
    planes = []
    for idx in gidx:
        dy, dx = divmod(idx, 2)
        plane = raw[dy::2, COL_LO:COL_HI].astype(np.float64) - float(blacks[idx])
        planes.append(plane.mean(axis=1))
    prof = np.empty(2 * len(planes[0]), dtype=np.float64)
    prof[0::2] = planes[0]
    prof[1::2] = planes[1] if len(planes) > 1 else planes[0]
    return prof


def profile_fft_period(prof: np.ndarray, lo: int, hi: int) -> tuple[float, float]:
    seg = prof[lo:hi]
    seg = seg - seg.mean()
    win = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg * win))
    freqs = np.fft.rfftfreq(len(seg))          # cycles per row
    k = int(np.argmax(spec[1:])) + 1          # skip DC
    # parabolic interpolation for sub-bin accuracy
    if 1 <= k < len(spec) - 1:
        a, b, c = spec[k - 1], spec[k], spec[k + 1]
        d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    else:
        d = 0.0
    f = freqs[k] + d * (freqs[1] - freqs[0])
    period_rows = 1.0 / f if f > 0 else float('inf')
    return period_rows, spec[k] / spec.max()


def band_metrics(prof: np.ndarray, lo: int, hi: int, rel: float = 0.7):
    seg = prof[lo:hi]
    med = np.median(seg)
    dark = seg < rel * med
    # contiguous dark runs
    runs, start = [], None
    for i, v in enumerate(dark):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(dark)))
    runs = [(s, e) for s, e in runs if e - s >= 3]
    centers = [(s + e) / 2 for s, e in runs]
    spacings = [b - a for a, b in zip(centers, centers[1:])] if len(centers) > 1 else []
    depths = [(float(np.min(seg[s:e]) / med)) for s, e in runs]
    return runs, spacings, depths


def main(ev_dir: str, out_json: str) -> int:
    ev = Path(ev_dir)
    frames = {
        # PWM calibration candidates at 625 us (known 720 Hz carrier)
        'pwm_2048_base': ['IMG_20260502_131219127.DNG', 'IMG_20260502_131223641.DNG'],
        'pwm_460_base': ['IMG_20260502_142005471.DNG', 'IMG_20260502_142009799.DNG'],
        # DC dip frames (cumulative-landed, deep dips visible)
        'dc_460_sweep625_dark': ['IMG_20260502_144127654.DNG'],
        'dc_460_sweep625_bright': ['IMG_20260502_144131564.DNG'],
        'dc_460_sweep800_dark': ['IMG_20260502_144150574.DNG'],
        'dc_460_sweep800_bright': ['IMG_20260502_144154498.DNG'],
        'dc_460_sweep125': ['IMG_20260502_144040387.DNG', 'IMG_20260502_144044314.DNG'],
        'dc_460_floor625_1': ['IMG_20260502_142038399.DNG'],
        'dc_460_floor625_3': ['IMG_20260502_142047233.DNG'],
        'dc_1024_cumul_1': ['IMG_20260502_135959128.DNG'],
        'dc_2048_cumul_2': ['IMG_20260502_135504423.DNG'],
    }
    out = {}
    for label, files in frames.items():
        for fn in files:
            prof = green_row_profile(ev / fn)
            per, amp = profile_fft_period(prof, ROW_LO, ROW_HI)
            runs, spacings, depths = band_metrics(prof, ROW_LO, ROW_HI)
            out[f'{label}:{fn}'] = {
                'fft_period_rows': round(float(per), 2),
                'fft_rel_amp': round(float(amp), 4),
                'dark_runs': [[int(s + ROW_LO), int(e + ROW_LO)] for s, e in runs[:12]],
                'dark_run_heights_rows': [int(e - s) for s, e in runs[:12]],
                'dark_spacings_rows': [round(float(x), 1) for x in spacings[:12]],
                'dark_depth_min_rel': [round(float(d), 3) for d in depths[:12]],
            }
            print(f'{label}:{fn}: per={per:.1f}rows amp={amp:.3f} '
                  f'bands={len(runs)} heights={[e-s for s,e in runs[:6]]} '
                  f'spacing={[round(x,1) for x in spacings[:6]]} '
                  f'depth={[round(d,2) for d in depths[:6]]}')
    Path(out_json).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: r11_band_analysis.py EVIDENCE_DIR OUT_JSON')
    sys.exit(main(sys.argv[1], sys.argv[2]))
