"""Replay R32 only: source is the camera preview of the *instrument* (no OLED frames).

Lag describes repetition on the instrument raster, not a photometric or Hz fit.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '06-tools/scope_pwm'))
from scope_native_lags import peaks

PHASES = ('wA dark wB wLo wHi propB force120 force144 force120ret rcp512 rcp6692 '
          'stock6692 stock512 stock3601 stock6873 stock6873Dim stock6873Ret '
          'grayW gray64 gray16 gray0 grayW2 preOff targetOff postOff').split()


def hwc(dump):
    modes = set(re.findall(r'activeMode=\{id=\d+, hwcId=(\d+),', dump.read_text()))
    if len(modes) != 1:
        raise ValueError(f'missing or conflicting active mode: {dump.name}')
    return modes.pop()


def figure(archive, output):
    # Same central portion of the scope grid, same preview frame index throughout.
    # Export a trace mask, not the camera view, EXIF or a reconstructed voltage.
    phases = ('stock512', 'rcp512', 'stock6692', 'rcp6692', 'force144', 'targetOff')
    canvas = Image.new('RGB', (720, 6 * 135 + 28), 'black')
    draw = ImageDraw.Draw(canvas)
    for j, phase in enumerate(phases):
        with Image.open(archive / f'{phase}-2.png') as im:
            a = np.array(im.convert('RGB').crop((147, 775, 850, 1055)), dtype=float)
        r, g, b = a.transpose(2, 0, 1)
        mask = (r > 1.35*b + 8) & (g > 1.25*b + 6) & (g > 70)
        trace = Image.fromarray(np.uint8(mask)*255).resize((703, 113), Image.Resampling.BOX)
        canvas.paste((255, 210, 40), (8, j*135 + 20, 711, j*135 + 133), trace)
        draw.text((8, j*135 + 3), phase, fill='white')
    draw.line((8, 822, 70, 822), fill='white', width=2)
    draw.text((82, 817), '1 horizontal division; vertical scale compressed, AC only', fill='white')
    canvas.save(output)


def analyze(archive, out):
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['phase', 'frame', 'hwc_pre', 'hwc_post', 'grid_lag_rho',
                     'upper_lag_rho', 'lower_lag_rho', 'lower_yellow_coverage'])
    for phase in PHASES:
        if phase == 'targetOff':
            for side in ('pre', 'post'):
                lines = {line.strip() for line in (archive / f'off-{side}.log').read_text().splitlines()}
                if not {'mScreenState=OFF', 'Off'} <= lines:
                    raise ValueError('unverified OFF window')
            modes = ['off', 'off']
        else:
            modes = [hwc(archive / f'{phase}-{side}.sf') for side in ('pre', 'post')]
        for n in (1, 2, 3):
            with Image.open(archive / f'{phase}-{n}.png') as im:
                if im.size != (1080, 2392):
                    raise ValueError('unexpected preview size')
                rgb = np.array(im.convert('RGB').crop((147, 852, 850, 1115)), dtype=float)
            r, g, b = rgb.transpose(2, 0, 1)
            yellow = (r + g) / 2 - b
            upper = yellow[:32]       # Y=852..883: above baseline
            lower = yellow[103:143]  # Y=955..994: below baseline
            grid = b[158:].mean(axis=0)  # Y=1010..1114: cross-check on grid
            signals = (grid, np.median(upper, axis=0), np.median(lower, axis=0))
            writer.writerow([phase, n, *modes, *(json.dumps(peaks(s)) for s in signals),
                             f'{np.mean(lower > 40):.4f}'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='private R32 capture directory')
    parser.add_argument('--figure', type=Path, help='export a representative trace mask')
    args = parser.parse_args()
    analyze(args.archive, sys.stdout)
    if args.figure:
        figure(args.archive, args.figure)
