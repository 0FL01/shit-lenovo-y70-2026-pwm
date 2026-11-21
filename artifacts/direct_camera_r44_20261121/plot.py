"""Plot the first qualified G1 exposure, not the smoothest of multiple releases."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.measure import ROI, read_sites


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('metrics',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--low',action='store_true');a=ap.parse_args()
    with a.metrics.open() as f:rows=list(csv.DictReader(f))
    im=Image.new('RGB',(960,435),'white');d=ImageDraw.Draw(im);d.text((24,14),'R44 | stock Flicker prevention under real HDR | G1 signal / local plateau | '+('low' if a.low else 'high')+' drive',fill='black')
    for j,ns in enumerate((200,312,500) if a.low else (125,200,312)):
        x0=42+j*313;xy=lambda x,y:(x0+(x+80)*1.58,300-y*183);d.text((x0,45),f'{312.5 if ns==312 else ns} us',fill='black')
        for y in (0,.25,.5,.75,1,1.25):
            _,v=xy(0,y);d.line((x0,v,x0+253,v),fill='#dbdbdb');d.text((x0-30,v-5),f'{y:g}',fill='#222222')
        for x in (-80,-40,0,40,80):
            u,_=xy(x,0);d.line((u,72,u,300),fill='#aaa' if x==0 else '#eee');d.text((u-9,308),str(x),fill='black')
        for i,(s,col) in enumerate((('off','#2664a7'),('on','#b54119'),('ret','#427741'))):
            ph=f"day_{s}{'Low' if a.low else ''}_{ns}";r=next((r for r in rows if r['phase']==ph and r['event_status']=='ok'),None)
            if not r:d.text((x0,334+17*i),f'{s}: no qualified event',fill=col);continue
            _,v=read_sites(a.frames/f"{ph}__{r['frame_n']}.dng",float(r['exposure_us']));g=np.convolve(v['G1'].mean(1)-float(r['black_dn']),np.ones(3)/3,'valid')/float(r['local_plateau_dn']);xx=2*np.arange(ROI[0]+1,ROI[1]-1)-float(r['fixed_g1_raw_y']);d.line([xy(x,y) for x,y in zip(xx,g) if abs(x)<=80],fill=col,width=2);d.text((x0,334+17*i),f"{s} #{r['frame_n']} | D={float(r['depth_pct']):.1f}%",fill=col)
    d.text((24,405),'X: RAW rows from the minimum of each exposure. Separate releases are aligned for shape, not relative phase.',fill='black');im.save(a.output)


if __name__=='__main__':main()
