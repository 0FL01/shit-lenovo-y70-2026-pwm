"""Verify simultaneous-field layout/receipts independently of the RAW notch analysis."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np
from PIL import Image

from light import read_dng,extract_metadata
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from direct_camera_r41_20261121.windows import snapshot,need


def classes(path):
    im=Image.open(path).convert('RGB');w,h=im.size;a=np.asarray(im.crop((w//4,h//4,3*w//4,3*h//4)));ids=np.full(a.shape[:2],-1,dtype=np.int8)
    for i,rgb in enumerate(((255,0,0),(0,255,0),(0,0,255))):ids[(a==rgb).all(axis=2)]=i
    return ids


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path,help='tile archive containing both layout PNGs, acquisition log, SF snapshots and frames/');p=ap.parse_args().archive
    lines=(p/'acquire.log').read_text().splitlines();it=iter(l for l in lines if l.startswith(('TILES ','PRE ','POST ','frame ')))
    a,b=[classes(p/(color+'.png')) for color in ('rgb','bgr')];good=(a>=0)&(b>=0);same=(b[good]==2-a[good]).mean();need(good.mean()>.85 and same>.98,'second layout did not exchange R and B')
    files=set();records=[]
    for color,ids in (('rgb',a),('bgr',b)):
        fractions=[float((ids==i).mean()) for i in range(3)];tag=next(it).split();need(tag[:4]==['TILES',color,'RGB','fractions'] and np.allclose(list(map(float,tag[4:])),fractions) and min(fractions)>.25,'pixel evidence differs')
        for suffix,ns,n in [('cal',1250000,3),('short',200000,4),('medium',500000,3)]:
            phase=color+'_'+suffix;pre=next(it);stamp=pre.split(' wake=');need(len(stamp)==2 and stamp[1].isdigit() and stamp[0]==f'PRE {phase} BL=6692 hwcId=0 ns={ns} rgb={color}','invalid opening receipt')
            for i in range(1,n+1):
                name=f'{phase}__{i}';f=p/'frames'/(name+'.dng');need(next(it)==f'frame {name} {f.stat().st_size}','missing/incorrect frame');files.add(f.name);_,tags=read_dng(f);m=extract_metadata(tags);need((m['iso'],m['focal_length_mm'],m['width'],m['height'],m['orientation'])==(6400,5.56,4080,3072,1) and abs(m['exposure_us']*1000-ns)<=1,'wrong physical capture')
            need(next(it)==pre.replace('PRE ','POST ',1)+f' count={n}','invalid closing receipt');s1=snapshot(p/(phase+'-pre.sf'));need(s1==snapshot(p/(phase+'-post.sf')),'SF changed');records.append((phase,color,6692,*s1[0],stamp[1],ns,n,*[round(x,5) for x in fractions],round(same,6)))
    need(next(it,None) is None and files=={f.name for f in (p/'frames').glob('*.dng')},'unbound events/files');out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('phase layout sysfs_bl hwc refresh group sf_rgb wake_epoch exposure_ns frames screenshot_r screenshot_g screenshot_b swapped_on_common_pure_pixels'.split());out.writerows(records)


if __name__=='__main__':main()
