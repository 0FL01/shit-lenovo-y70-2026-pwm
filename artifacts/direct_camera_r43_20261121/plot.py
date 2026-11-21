"""Plot first qualified SDR/HDR profiles at matching shutters; offsets are not times."""
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from measure import ROI, read_sites


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('metrics',type=Path);ap.add_argument('out',type=Path);a=ap.parse_args()
    with a.metrics.open() as f: rows=list(csv.DictReader(f))
    im=Image.new('RGB',(960,450),'white');d=ImageDraw.Draw(im);d.text((25,13),'R43 | G1 / local plateau | 30 fps input | first qualified exposure per scene',fill='black')
    for j,us in enumerate((125,200,312)):
        x0=43+j*313;xy=lambda x,y:(x0+(80+x)*1.58,300-y*185);d.text((x0,43),f'{312.5 if us==312 else us} us',fill='black')
        for y in (0,.25,.5,.75,1,1.25):
            _,v=xy(0,y);d.line((x0,v,x0+253,v),fill='#dadada');d.text((x0-30,v-5),f'{y:g}',fill='black')
        for x in (-80,-40,0,40,80):
            u,_=xy(x,0);d.line((u,68,u,300),fill='#aaa' if x==0 else '#eee');d.text((u-8,307),str(x),fill='black')
        for i,(s,color) in enumerate([('sdr','#176199'),('sdrHigh','#327746'),('sdrMatch','#78509c'),('hdr','#bd481a')]):
            ph=f'day_{s}_{us}';r=next((r for r in rows if r['phase']==ph and r['event_status']=='ok'),None)
            if not r:continue
            _,v=read_sites(a.frames/f"{ph}__{r['frame_n']}.dng",float(r['exposure_us']));profile=np.convolve(v['G1'].mean(1)-float(r['black_dn']),np.ones(3)/3,'valid')/float(r['local_plateau_dn']);pos=2*np.arange(ROI[0]+1,ROI[1]-1)-float(r['fixed_g1_raw_y']);d.line([xy(x,y) for x,y in zip(pos,profile) if abs(x)<=80],fill=color,width=2);d.text((x0,334+16*i),f"{s} #{r['frame_n']}  D={float(r['depth_pct']):.1f}%",fill=color)
    d.text((24,414),'sdrMatch: same BL and matched mean light. X: native RAW rows from each frame\'s trough (shape alignment only).',fill='black');im.save(a.out)


if __name__=='__main__':main()
