"""Make a private contact sheet for reading three badges; do not commit or publish its output."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
def sheet(root,first,last,out):
    ps=sorted(root.glob('P[0-9][0-9]_s[0-9].png'))[first:last]
    if not ps:raise ValueError('empty range')
    result=Image.new('RGB',(260,len(ps)*38),'#222222');draw=ImageDraw.Draw(result)
    for j,p in enumerate(ps):
        with Image.open(p) as im:
            y=38*j;draw.text((0,y+7),p.stem,fill='white');x=65
            for box in ((188,1295,233,1325),(283,1292,349,1323),(389,1291,447,1324)):
                patch=im.crop(box);result.paste(patch,(x,y));x+=patch.width+4
    result.save(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('first',type=int);p.add_argument('last',type=int);p.add_argument('out',type=Path)
    a=p.parse_args();sheet(a.root,a.first,a.last,a.out)
