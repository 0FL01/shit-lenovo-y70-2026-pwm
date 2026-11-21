"""Plot the first release at 312.5 us from each R45 state, on the same DN axes."""
import argparse
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.measure import ROI, read_sites


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path); ap.add_argument('output', type=Path)
    args = ap.parse_args()
    traces = []
    for z in ('off', 'on', 'ret'):
        m, raw = read_sites(args.frames/f'day_{z}Low_312__1.dng', 312.5)
        g = raw['G1'].mean(axis=1) - m['black_levels'][0]
        traces.append(np.convolve(g, np.ones(3)/3, 'valid'))
    im = Image.new('RGB', (920, 460), 'white'); d = ImageDraw.Draw(im)
    d.text((26, 12), 'R45   |   HDR / BL 3593   |   G1 signal above tagged black [DN]   |   312.5 us', fill='black')
    hi = 10*np.ceil(max(t.max() for t in traces)/10); low = min(0, int(np.floor(min(t.min() for t in traces))))
    for i,(t,label,col) in enumerate(zip(traces, ('OFF', 'ON', 'returned OFF'), ('#305e94','#a8431b','#3a7540'))):
        base = 151 + i*128
        y = lambda v: base - 92*(v-low)/(hi-low)
        d.text((40,base-115), label+'   #1', fill=col)
        for v in (0, 20, hi):
            d.line((54,y(v),884,y(v)), fill='#dddddd'); d.text((24,y(v)-5),f'{v:g}',fill='#444444')
        d.line([(54+j*830/(len(t)-1),y(v)) for j,v in enumerate(t)], fill=col, width=2)
    d.text((54,420),str(2*(ROI[0]+1)),fill='black'); d.text((850,420),str(2*(ROI[1]-2)),fill='black')
    d.text((280,435),'Native RAW row; separate releases, phase not aligned',fill='black'); im.save(args.output)


if __name__ == '__main__':
    main()
