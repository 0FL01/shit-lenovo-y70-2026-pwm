"""Compare three first 312.5-us releases at native sensor coordinates, not aligned phase."""
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
    args = ap.parse_args(); curves = []
    for leg in ('on120A', 'on144B', 'on120C'):
        m, sites = read_sites(args.frames/f'day_{leg}_312__1.dng', 312.5)
        curve = np.convolve(sites['G1'].mean(1) - m['black_levels'][0], np.ones(3)/3, mode='valid')
        curves.append(curve)
    lo = min(0, np.floor(min(t.min() for t in curves)))
    hi = 10*np.ceil(max(t.max() for t in curves)/10)
    im = Image.new('RGB', (960, 462), 'white'); d = ImageDraw.Draw(im)
    d.text((24,10),'R46  |  HDR / BL 3593 / native ON  |  first release at 312.5 us  |  G1 above tagged black [DN]',fill='black')
    for i,(trace,leg,color) in enumerate(zip(curves,('120 Hz A','144 Hz B','120 Hz C'),('#305e94','#a8431b','#3a7540'))):
        bottom = 145+131*i; y=lambda v:bottom-95*(v-lo)/(hi-lo)
        d.text((50,bottom-115),leg,fill=color)
        for v in (0,20,hi):
            d.line((52,y(v),925,y(v)),fill='#dddddd'); d.text((20,y(v)-5),f'{v:g}',fill='#444444')
        d.line([(52+j*873/(len(trace)-1),y(v)) for j,v in enumerate(trace)],fill=color,width=2)
    d.text((50,415),str(2*(ROI[0]+1)),fill='black'); d.text((895,415),str(2*(ROI[1]-2)),fill='black')
    d.text((290,438),'Native RAW row; separate releases. HWC refresh is not PWM.',fill='black'); im.save(args.output)


if __name__=='__main__':
    main()
