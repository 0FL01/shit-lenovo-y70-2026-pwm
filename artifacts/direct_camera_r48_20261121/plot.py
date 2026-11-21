#!/usr/bin/env python3
"""Plot R48 DAY G1 depths and within-guard median differences offline (Pillow, DejaVu Sans).

From this directory: python3 -B plot.py compare.csv frames.csv boundary.png
"""

import argparse
from collections import defaultdict
import csv
from math import ceil, floor, isclose
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw, ImageFont


EXPOSURES = (125, 200, 312.5)
LEVELS = tuple(range(14055, 14059))
LEGS = ('offA', 'offB', 'offC', 'offD')
RAMPS = (
    ('forward', '', '#305e94', '#b4c8dc', 'circle', 'Forward (up)'),
    ('return', 'r', '#a8431b', '#e5b8a4', 'square', 'Reverse (down)'),
)
MIN_N = 3
INK, MUTED = '#17212d', '#4c5865'
GRID, RULE = '#e0e5e9', '#84909c'


def read_data(compare_path, frames_path):
    with compare_path.open(newline='', encoding='utf-8') as f:
        rows = [r for r in csv.DictReader(f) if r['metric'] == 'depth_pct']
    summary = {float(r['exposure_us']): r for r in rows}
    if len(rows) != 3 or set(summary) != set(EXPOSURES):
        raise ValueError('expected one G1 depth summary per DAY exposure')
    depths, totals = defaultdict(list), defaultdict(int)
    day_legs = {leg + ramp[1] for leg in LEGS for ramp in RAMPS}
    with frames_path.open(newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['group'] != 'day' or r['scene'] not in day_legs:
                continue  # CAL and separate same-code sham are not physical edge endpoints.
            key = float(r['exposure_us']), r['scene']
            totals[key] += 1
            if r['event_status'] == 'ok':
                depths[key].append(float(r['depth_pct']))
    for us, row in summary.items():
        guards = set()
        for _, suffix, *_ in RAMPS:
            ramp_guards = {row[f'{leg}{suffix}_guard'] for leg in LEGS}
            if len(ramp_guards) != 1 or '' in ramp_guards or ramp_guards & guards:
                raise ValueError(f'{us:g} µs: expected separate up/down guards')
            guards.update(ramp_guards)
            for level, leg in zip(LEVELS, LEGS):
                phase = leg + suffix
                v = depths[us, phase]
                if (int(row[phase + '_dbv']) != level
                        or int(row[phase + '_total']) != totals[us, phase]
                        or int(row[phase + '_qualified']) != len(v)
                        or (v and not isclose(median(v), float(row[phase + '_median']), abs_tol=1e-6))):
                    raise ValueError(f'{us:g} µs / {phase}: frames and comparison disagree')
    return summary, depths


def render(summary, depths):
    # Supersample shapes and text, then write a compact antialiased PNG.
    scale = 2
    width, height = 1070, 538
    im = Image.new('RGB', (width*scale, height*scale), 'white')
    d = ImageDraw.Draw(im)

    def text(x, y, label, size=13, color=INK, *, bold=False, anchor='lm'):
        font = ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size*scale)
        d.text((x*scale, y*scale), label, font=font, fill=color, anchor=anchor)

    def line(x1, y1, x2, y2, color=GRID, width=1):
        d.line(tuple(round(v*scale) for v in (x1, y1, x2, y2)), fill=color, width=width*scale)

    def marker(x, y, shape, color, *, filled=True, radius=5):
        if shape == 'missing':
            line(x-radius, y-radius, x+radius, y+radius, color, 2)
            line(x-radius, y+radius, x+radius, y-radius, color, 2)
            return
        bbox = tuple(round(v*scale) for v in (x-radius, y-radius, x+radius, y+radius))
        draw = d.ellipse if shape == 'circle' else d.rectangle
        draw(bbox, fill=color if filled else 'white', outline=color, width=2*scale)

    text(25, 23, 'R48 | SDR near DBV 14056', 23, bold=True)
    text(26, 48, 'Fixed white field · HWC 0 / 120 Hz · stock Flicker prevention OFF', 13, MUTED)
    for x, ramp in zip((740, 898), RAMPS):
        marker(x, 35, ramp[4], ramp[2])
        text(x+13, 35, ramp[5], 13)
    line(25, 65, 1046, 65)
    text(108, 86, 'Absolute G1 notch depth (%)', 15, bold=True)
    text(641, 86, 'Δ median depth: higher DBV − lower DBV (pp)', 15, bold=True)

    depth_x = (153, 276, 399, 522)
    delta_x = (704, 842, 982)
    for i, us in enumerate(EXPOSURES):
        row = summary[us]
        top, bottom = 108+113*i, 204+113*i
        text(25, top+8, f'{us:g} µs', 12, bold=True)
        all_depths = [v for leg in LEGS for ramp in RAMPS for v in depths[us, leg+ramp[1]]]
        lo = floor(min(all_depths, default=0) - 0.15)
        hi = ceil(max(all_depths, default=100) + 0.15)

        def y_depth(value):
            return bottom - (bottom-top)*(value-lo)/(hi-lo)

        for tick in range(lo, hi+1, max(1, (hi-lo)//4)):
            y = y_depth(tick)
            line(108, y, 576, y)
            text(101, y, str(tick), 12, MUTED, anchor='rm')

        delta_values = [float(row[f'{a}_{b}_{ramp[0]}_delta_median'])
                        for a, b in zip(LEVELS, LEVELS[1:]) for ramp in RAMPS
                        if row[f'{a}_{b}_{ramp[0]}_delta_median']]
        limit = max(3.55, max(map(abs, delta_values), default=0) + 0.35)

        def y_delta(value):
            return (top+bottom)/2 - (bottom-top)*value/(2*limit)

        d.rectangle((918*scale, top*scale, 1046*scale, bottom*scale), fill='#f1f4f6')
        for tick, label in ((3, '+3'), (0, '0'), (-3, '−3')):
            y = y_delta(tick)
            if tick == 0:
                line(641, y, 1046, y, RULE)
            else:
                for x in range(641, 1046, 9):
                    line(x, y, min(x+4, 1046), y, RULE)
            text(630, y, label, 12, MUTED, anchor='rm')

        for j, (direction, suffix, col, pale, shape, _) in enumerate(RAMPS):
            offset = (-13, 13)[j]
            for x, leg in zip(depth_x, LEGS):
                values = depths[us, leg+suffix]
                for k, val in enumerate(values):
                    jitter = (k-(len(values)-1)/2)*5
                    marker(x+offset+jitter, y_depth(val), 'circle', pale, radius=2.5)
                if values:
                    marker(x+offset, y_depth(median(values)), shape, col, filled=len(values) >= MIN_N)
                else:
                    marker(x+offset, bottom-6, 'missing', col, radius=4)

            for k, (x, lower, higher) in enumerate(zip(delta_x, LEVELS, LEVELS[1:])):
                a, b = (leg+suffix for leg in LEGS[k:k+2])
                key = f'{lower}_{higher}_{direction}'
                value = row[f'{key}_delta_median']
                count = min(len(depths[us, a]), len(depths[us, b]))
                if row[f'{key}_high_minus_low'] != f'{b}-{a}' or bool(value) != bool(count):
                    raise ValueError(f'{us:g} µs / {key}: invalid edge endpoints')
                if not value:
                    marker(x+offset, bottom-6, 'missing', col, radius=4)
                    continue
                delta = float(value)
                if not isclose(delta, median(depths[us, b])-median(depths[us, a]), abs_tol=1e-6):
                    raise ValueError(f'{us:g} µs / {key}: median difference disagrees with frames')
                marker(x+offset, y_delta(delta), shape, col, filled=count >= MIN_N)

    for x, level in zip(depth_x, LEVELS):
        text(x, 445, str(level), 12, anchor='mm')
    text(337, 465, 'Measured DBV (separate depth scale per shutter)', 12, MUTED, anchor='mm')
    for x, a, b in zip(delta_x, LEVELS, LEVELS[1:]):
        text(x, 445, f'{a}–{b}', 12, anchor='mm')
    text(delta_x[1]-69, 465, 'Candidate edges', 12, MUTED, anchor='mm')
    text(delta_x[2], 465, 'Neighbor control', 12, MUTED, anchor='mm')

    line(25, 482, 1046, 482)
    text(25, 501, 'Left: small dots = qualified RAWs; large markers = medians. Open = n < 3; × = no value.', 12, MUTED)
    text(25, 521, '312.5 µs: forward 14055 had 2/4 qualified RAWs; the first edge is unresolved. Δ values stay within each guard.',
         12, MUTED)
    return im.resize((width, height), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compare_csv', type=Path)
    parser.add_argument('frames_csv', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    render(*read_data(args.compare_csv, args.frames_csv)).save(args.output)


if __name__ == '__main__':
    main()
