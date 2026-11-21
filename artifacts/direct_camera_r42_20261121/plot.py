"""Plot the first qualified day exposure of each load, from the measured G1 rows."""
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from measure import ROI, read_sites


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('csv',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    with a.csv.open() as f:rows=list(csv.DictReader(f))
    im=Image.new('RGB',(960,420),'white');d=ImageDraw.Draw(im)
    d.text((20,12),'R42 | Same local white patch, different distant surround | G1 signal / own plateau',fill='black')
    for col,(group,us) in enumerate([('d200',200),('d312',312.5),('d500',500)]):
        left=45+310*col;right=left+255;xy=lambda x,y:(left+(x+80)*255/160,305-y*190)
        d.text((left,43),f'{us:g} us',fill='black')
        for tick in (0,.25,.5,.75,1,1.25):
            _,y=xy(0,tick);d.line((left,y,right,y),fill='#e2e2e2');d.text((left-30,y-6),f'{tick:g}',fill='black')
        for tick in (-80,-40,0,40,80):
            x,_=xy(tick,0);d.line((x,68,x,305),fill='#aaa' if tick==0 else '#eee');d.text((x-9,312),str(tick),fill='black')
        for j,(scene,color) in enumerate([('core','#2160a3'),('loaded','#ba4e17')]):
            ph=group+'_'+scene;r=next((r for r in rows if r['phase']==ph and r['event_status']=='ok'),None)
            if r is None:continue
            _,v=read_sites(a.frames/f"{ph}__{r['frame_n']}.dng",us);g=v['G1'].mean(1)-float(r['black_dn']);g=np.convolve(g,np.ones(3)/3,'valid')/float(r['local_plateau_dn']);x=2*np.arange(ROI[0]+1,ROI[1]-1)-int(float(r['fixed_g1_raw_y']));d.line([xy(u,y) for u,y in zip(x,g) if abs(u)<=80],fill=color,width=2);d.text((left,338+16*j),f"{scene} #{r['frame_n']}  D={float(r['depth_pct']):.1f}%",fill=color)
    d.text((25,390),'X: RAW rows from each frame\'s own trough. Separate shutter releases; alignment is for shape, not relative phase.',fill='black');im.save(a.output)


if __name__=='__main__':main()
