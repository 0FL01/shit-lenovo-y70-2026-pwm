#!/usr/bin/env python3
"""Render the R49 4 ms evidence with Pillow. From this directory:

    python3 -B repeats.py ../../../../private-bench-evidence/direct-r49-20261121/frames --rows \
      | python3 -B plot.py frames.csv owner_frames.csv optics.png
"""

import argparse
import csv
from math import ceil, isfinite
from pathlib import Path
from statistics import mean, median
import sys

from PIL import Image, ImageDraw, ImageFont


INK, MUTED, GRID, RULE = '#17212d', '#4c5865', '#e0e5e9', '#84909c'
COLORS = {'A': '#305e94', 'B': '#a8431b', 'O': '#565e6b'}
PALE = {'A': '#c7d8e9', 'B': '#ebc0aa', 'O': '#d5dae0'}
ROI = ('630', '1250', '754', '799')
NATIVE_ROWS = tuple(range(1262, 2498, 2))


def read_means(path, leg):
    phase = f'day_{leg}_4000'
    values = {}
    with path.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['phase'] != phase:
                continue
            n, value = int(row['frame_n']), float(row['mean_dn'])
            if (n in values or row['group'] != 'day' or row['scene'] != leg
                    or float(row['exposure_us']) != 4000 or row['gate'] != 'ok'
                    or int(row['clip_n']) or int(row['floor_n']) or not isfinite(value)
                    or tuple(row[k] for k in ('y0', 'y1', 'x0', 'x1')) != ROI):
                raise ValueError(f'{phase}: invalid 4 ms frame row')
            values[n] = value
    if set(values) != {1, 2, 3, 4}:
        raise ValueError(f'{phase}: expected exactly four releases')
    return [values[n] for n in range(1, 5)]


def read_spans(stream):
    phases = {f'day_{leg}_4000': leg for leg in 'AB'}
    spans = {leg: {} for leg in 'AB'}
    for row in csv.DictReader(stream):
        leg = phases[row['phase']]
        y, span = int(row['raw_y']), float(row['full_span_dn'])
        if y in spans[leg] or not isfinite(span) or span < 0:
            raise ValueError(f'{leg}: invalid or repeated row {y}')
        spans[leg][y] = span
    if any(tuple(sorted(data)) != NATIVE_ROWS for data in spans.values()):
        raise ValueError('expected complete fixed native rows for A and B from repeats.py --rows')
    return spans


def render(means, spans):
    scale = 2
    width, height = 960, 414
    im = Image.new('RGB', (width*scale, height*scale), 'white')
    d = ImageDraw.Draw(im)
    fonts = {}

    def coords(*xy):
        return tuple(round(v*scale) for v in xy)

    def text(x, y, label, size=13, color=INK, *, bold=False, anchor='lm'):
        key = size, bold
        if key not in fonts:
            fonts[key] = ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size*scale)
        d.text(coords(x, y), label, font=fonts[key], fill=color, anchor=anchor)

    def line(x1, y1, x2, y2, color=GRID, weight=1):
        d.line(coords(x1, y1, x2, y2), fill=color, width=weight*scale)

    def box(x1, y1, x2, y2, color):
        d.rectangle(coords(x1, y1, x2, y2), fill=color)

    text(24, 25, 'R49 | White field at 4 ms', 24, bold=True)
    text(25, 50, 'Same shutter and fixed native ROI · DBV 512 · 4 original RAW releases per group', 13, MUTED)
    line(24, 66, 936, 66)
    text(24, 88, 'Mean G1 signal above tagged black (DN)', 15, bold=True)
    text(506, 88, 'Same-row span across four releases (DN)', 15, bold=True)

    left, right, top, bottom = 62, 456, 118, 316
    ymax = 100*ceil((max(max(v) for v in means.values()) + 30)/100)

    def bar_y(v):
        return bottom - (bottom-top)*v/ymax

    box(310, 109, right, 361, '#f1f3f6')
    for tick in range(0, ymax+1, 100):
        y = bar_y(tick)
        line(left, y, right, y, RULE if tick == 0 else GRID)
        text(left-8, y, str(tick), 11, MUTED, anchor='rm')
    for leg, x, label, detail in zip(
        'ABO', (128, 249, 383), ('A · baseline', 'B · changed', 'Owner after restore'),
        ('9E = 11', '9E = 91', 'Separate · not cycle R'),
    ):
        values = means[leg]
        average = mean(values)
        box(x-32, bar_y(average), x+32, bottom-1, PALE[leg])
        for dx, value in zip((-21, -7, 7, 21), values):
            y = bar_y(value)
            d.ellipse(coords(x+dx-3.5, y-3.5, x+dx+3.5, y+3.5), fill=COLORS[leg], outline='white', width=scale)
        text(x, bar_y(max(values))-15, f'{average:.2f}', 15, COLORS[leg], bold=True, anchor='mm')
        text(x, 334, label, 12, bold=True, anchor='mm')
        text(x, 352, detail, 11, MUTED, anchor='mm')

    left, right = 541, 936
    ymax = 20*ceil(max(max(v.values()) for v in spans.values())/20)

    def row_x(y):
        return left + (right-left)*(y-NATIVE_ROWS[0])/(NATIVE_ROWS[-1]-NATIVE_ROWS[0])

    def span_y(v):
        return bottom - (bottom-top)*v/ymax

    for tick in range(0, ymax+1, 20):
        y = span_y(tick)
        line(left, y, right, y, RULE if tick == 0 else GRID)
        text(left-8, y, str(tick), 11, MUTED, anchor='rm')
    for tick in range(1400, 2500, 200):
        x = row_x(tick)
        line(x, top, x, bottom)
        text(x, 331, str(tick), 11, MUTED, anchor='mm')
    for leg, x in zip('AB', (541, 742)):
        data = spans[leg]
        points = [coords(row_x(y), span_y(data[y])) for y in NATIVE_ROWS]
        d.line(points, fill=COLORS[leg], width=scale)
        line(x, 372, x+18, 372, COLORS[leg], 2)
        text(x+25, 372, f'{leg} · median {median(data.values()):.1f} DN', 12)
    text((left+right)/2, 350, 'Native RAW row (unrotated)', 12, anchor='mm')
    text(24, 389, 'Dots: individual ROI means. Bars: average of four dots.', 11, MUTED)
    text(506, 388, 'Max − min of 3-G1-row averages; no alignment or scaling.', 11, MUTED)
    return im.resize((width, height), Image.Resampling.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path)
    ap.add_argument('owner_frames', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    try:
        means = {leg: read_means(args.frames if leg != 'O' else args.owner_frames, leg) for leg in 'ABO'}
        render(means, read_spans(sys.stdin)).save(args.output)
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        ap.error(str(exc))


if __name__ == '__main__':
    main()
