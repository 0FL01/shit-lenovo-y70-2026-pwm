"""Show qualified short-RAW minima from the primary APL return; no interpolation of absent events."""
import argparse
import csv
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames_csv',type=Path); ap.add_argument('output',type=Path)
    args=ap.parse_args()
    with args.frames_csv.open() as f:
        rows=[r for r in csv.DictReader(f) if r['group']=='day' and r['event_status']=='ok']
    im=Image.new('RGB',(930,340),'white'); d=ImageDraw.Draw(im)
    d.text((18,12),'R47 | G1 notch depth [%] at the real stock APL boundary | independent releases and medians',fill='black')
    for j,(token,lo,hi) in enumerate([('125',96,100),('200',89,93),('312',62,66)]):
        start=55+310*j; y=lambda v:245-(v-lo)*165/(hi-lo)
        d.text((start,48),f'{312.5 if token=="312" else token} us',fill='black')
        for v in range(lo,hi+1):
            d.line((start-8,y(v),start+220,y(v)),fill='#dddddd'); d.text((start-36,y(v)-5),str(v),fill='#414141')
        for i,(leg,name,col) in enumerate([('offA','16000 A','#305e94'),('offB','16001 B','#a8431b'),('offC','16000 C','#3a7540')]):
            pts=[float(r['depth_pct']) for r in rows if r['phase']==f'day_{leg}_{token}'];x=start+28+i*73
            d.text((x-23,255),name,fill=col)
            for k,v in enumerate(pts):
                xx=x+(k-(len(pts)-1)/2)*6; d.ellipse((xx-2.5,y(v)-2.5,xx+2.5,y(v)+2.5),fill=col)
            if pts:d.line((x-16,y(median(pts)),x+16,y(median(pts))),fill=col,width=2)
    d.text((18,300),'A/C: native APL OFF. B: native APL ON. Different y-axis ranges by shutter; positions do not imply frequency.',fill='black')
    im.save(args.output)


if __name__=='__main__':
    main()
