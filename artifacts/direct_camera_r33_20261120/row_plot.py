"""Draw the direct-camera row traces, without publishing the DNGs or EXIF."""
import argparse
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pwm_06x_dng_bench_20261119'))
from analyze_2d_modulation import load_bayer2x2_green


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('phases', nargs='+', help='public phase labels; second frame of each')
    args = p.parse_args()
    rows = []
    for phase in args.phases:
        bayer, _ = load_bayer2x2_green(args.frames / f'{phase}__2.dng')
        # Same fixed ROI as the measurement. No flat, auto-levels or per-trace gain.
        rows.append(bayer[630:1370, 540:720].mean(axis=1))
    ceil = max(10, int(np.ceil(max(max(x) for x in rows)/10))*10)
    canvas = Image.new('RGB', (840, 52+115*len(rows)), 'white')
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 2), 'Direct RAW on OLED: row mean (DN above DNG black); one frame per phase, not time aligned.', fill='black')
    for i, (phase, row) in enumerate(zip(args.phases, rows)):
        y = 31 + i*115
        draw.text((72, y), phase, fill='black')
        for dn in [0, ceil/2, ceil]:
            at = y+100-round(78*dn/ceil)
            draw.line((69, at, 809, at), fill='#cbd5dc')
            draw.text((27, at-7), f'{dn:g}', fill='#354651')
        draw.line([(70+j, y+100-78*v/ceil) for j, v in enumerate(row)], fill='#174e79', width=2)
    draw.text((69, canvas.height-21), '1260', fill='black')
    draw.text((370, canvas.height-21), 'physical sensor row', fill='black')
    draw.text((783, canvas.height-21), '2738', fill='black')
    canvas.save(args.output)


if __name__ == '__main__':
    main()
