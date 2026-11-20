"""Export one representative evening row profile per phase; no photos or EXIF."""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

from measure import block_image


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames',type=Path); p.add_argument('flat_map',type=Path)
    p.add_argument('figure',type=Path); p.add_argument('phases',nargs='+'); args=p.parse_args()
    mapping=json.loads(args.flat_map.read_text()); roi=(630,1370,540,720)
    traces=[]; out=csv.writer(sys.stdout,lineterminator='\n'); out.writerow(('phase','frame_n','raw_y_start','row_mean_dn','flat_row_over_mean'))
    for ph in args.phases:
        flat=np.median([block_image(f,roi) for f in sorted(args.frames.glob(mapping[ph]+'__*.dng'))],axis=0)
        a=block_image(args.frames/f'{ph}__2.dng',roi)
        if flat.min()<=20 or a.mean()<20: raise ValueError('unqualified panel/reference signal')
        raw=a.mean(axis=1); r=(a/flat).mean(axis=1); r/=r.mean(); traces.append(r)
        for j,(v,ratio) in enumerate(zip(raw,r)):out.writerow((ph,2,1260+10*j,round(v,5),round(ratio,6)))
    # Identical vertical scale for every trace; place each row at its native position.
    cap=max(1.5,float(np.ceil(2*max(max(r) for r in traces)))/2)
    im=Image.new('RGB',(840,42+108*len(traces)),'white');d=ImageDraw.Draw(im)
    d.text((8,2),'Evening RAW: row / same-scene flat, normalized to mean = 1; frame #2 per window',fill='black')
    for i,(ph,r) in enumerate(zip(args.phases,traces)):
        y=32+108*i;d.text((68,y-7),ph,fill='black')
        for value in (0,1,cap):
            pos=y+81-64*value/cap; d.line((69,pos,806,pos),fill='#cbd5dc');d.text((32,pos-6),f'{value:g}',fill='black')
        d.line([(70+5*j,y+81-64*v/cap) for j,v in enumerate(r)],fill='#174e79',width=2)
    d.text((70,im.height-18),'1260',fill='black');d.text((357,im.height-18),'sensor row (not time)',fill='black');d.text((773,im.height-18),'2730',fill='black'); im.save(args.figure)


if __name__=='__main__': main()
