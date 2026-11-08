#!/usr/bin/env python3
"""Quick optical band measurement from the Pacman Open Camera preview.

Usage: pacman_bands.py CAMERA_TRANSPORT OUT_PNG [X0 X1]
Takes one screencap of the preview (landscape, rolling-shutter rows vertical),
averages columns X0..X1 and reports the strongest band periods in pixels.
Periods are camera pixels, not Hz; compare states under identical camera setup.
"""
import io
import json
import subprocess
import sys

import numpy as np
from PIL import Image


def measure(transport, out_png, x0=1150, x1=1750):
    png = subprocess.run(['adb', '-t', transport, 'exec-out', 'screencap', '-p'],
                         capture_output=True, check=True, timeout=20).stdout
    open(out_png, 'wb').write(png)
    im = np.asarray(Image.open(io.BytesIO(png)).convert('L'), dtype=float)
    prof = im[:, x0:x1].mean(axis=1)
    n = len(prof)
    detr = prof - np.convolve(prof, np.ones(301) / 301, mode='same')
    detr = detr[160:n - 160]
    w = detr * np.hanning(len(detr))
    spec = np.abs(np.fft.rfft(w, 8 * len(w)))
    freqs = np.fft.rfftfreq(8 * len(w))
    valid = (freqs > 1 / 400) & (freqs < 1 / 6)
    idx = np.where(valid)[0]
    peaks = [i for i in idx[1:-1] if spec[i] >= spec[i - 1] and spec[i] >= spec[i + 1]]
    peaks.sort(key=lambda i: -spec[i])
    top = [{'period_px': round(1 / freqs[i], 2), 'amp': round(float(spec[i]), 1)} for i in peaks[:5]]
    return {'mean': round(float(prof.mean()), 2), 'std_detrended': round(float(detr.std()), 3),
            'peaks': top}


if __name__ == '__main__':
    args = sys.argv[1:]
    xs = [int(a) for a in args[2:4]] if len(args) >= 4 else []
    print(json.dumps(measure(args[0], args[1], *xs)))
