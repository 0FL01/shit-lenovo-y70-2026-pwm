"""R41: signed camera-Y matching; per-frame flat-corrected residual on primary CFA site and Y.

The two reported bands use different coordinates: a given native CFA site, or
the fixed color-matrix projection. A small Y signal is not promoted by a bright
blue site. All 5x5-flat blocks must be >20 DN. Three independent same-scene long
frames; each long control uses only the other long frames (leave-one-out).
"""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

from light import ROI,read_dng,signal
from dng_qualify import extract_metadata


SITE={'ref':0,'ret':0,'neutral':0,'red':2,'green':0,'blue':1,'bluecheck':1,'yellow':0}
NAMES=('G1','B','R','G2')


def planes(path,i):
    raw,t=read_dng(path);m=extract_metadata(t);_,Y=signal(raw,t)
    y0,y1,x0,x1=ROI;dy,dx=divmod(i,2);site=raw[2*y0+dy:2*y1:2,2*x0+dx:2*x1:2].astype(float)-m['black_levels'][i]
    return {'Ycam':Y,NAMES[i]:site.reshape((y1-y0)//5,5,(x1-x0)//5,5).mean(axis=(1,3))}


def correction(blocks,flat):
    q=blocks/flat;l,h=np.percentile(q.mean(axis=1),(1,90));a,b=np.percentile(q,(5,95))
    return 100*(1-l/h),100*(b-a)/(b+a)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('windows',type=Path);ap.add_argument('--same-blue',action='store_true',help='pair the two blue-only scenes by signal on the same B site');a=ap.parse_args()
    with a.windows.open() as f:ws={z['phase']:z for z in csv.DictReader(f)}
    def frames(ph,i):return [planes(a.frames/f'{ph}__{j}.dng',i) for j in range(1,1+int(ws[ph]['frames']))]
    key_light='B' if a.same_blue else 'Ycam'
    def level(ph):return float(np.median([z[key_light].mean() for z in frames(ph,1 if a.same_blue else 0)]))
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('group scene sysfs_bl match_metric full_dn black_dn net_vs_ref_pct full_vs_ref_pct flat_ns phase exposure_ns frame_n metric mean_dn gate row_dip_pct block_contrast_pct dark_halfspan_pct'.split())
    for group,i in ({'low':1,'high':1} if a.same_blue else SITE).items():
        prefix=('u_' if a.same_blue else 'e_')+group;ref=prefix+'_flat'
        if ref not in ws:continue
        w=ws[ref];long=int(w['exposure_ns']);suffix='25' if long==25000000 else '8'
        wk='e_ref_flat' if suffix=='25' else 'e_ref8_flat';bg_prefix='e_low' if group=='ref' else 'e_ret' if group=='ret' else 'e_high';bg=bg_prefix+'_black'+suffix;wblack='e_low_black'+suffix
        if a.same_blue:wk='u_low_flat';bg=prefix+'_black';wblack='u_low_black'
        if not all(ws[k]['exposure_ns']==str(long) for k in (wk,bg,wblack)):raise ValueError('unmatched mean exposure')
        if ws[bg]['scene_rgb']!='000000' or ws[bg]['sysfs_bl']!=w['sysfs_bl']:raise ValueError('bad scene black')
        gross=level(ref);black=level(bg);target=level(wk);target_bg=level(wblack);netdiff=100*((gross-black)/(target-target_bg)-1);grossdiff=100*(gross/target-1)
        base=frames(ref,i)
        if len(base)<3:raise ValueError('need three independent flats')
        for end in (('flat','other','ten') if a.same_blue else ('flat','short','other')):
            ph=prefix+'_'+end;z=ws[ph];ns=int(z['exposure_ns']);arr=base if end=='flat' else frames(ph,i)
            if (z['scene_rgb'],z['sysfs_bl'],z['hwc_both'],z['wake_epoch'])!=(w['scene_rgb'],w['sysfs_bl'],w['hwc_both'],w['wake_epoch']) or (end!='flat' and ns>=long):raise ValueError('invalid flat association')
            darkph=bg if end=='flat' else ('e_low' if group in ('ref','ret','low') else 'e_high')+'_black'+('4' if end=='short' else 'other')
            if end!='ten' and (ws[darkph]['exposure_ns']!=str(ns) or ws[darkph]['sysfs_bl']!=w['sysfs_bl'] or ws[darkph]['scene_rgb']!='000000'):raise ValueError('bad dark interval')
            darks=[] if end=='ten' else frames(darkph,i)
            for j,imgs in enumerate(arr):
                for key,blocks in imgs.items():
                    flat=np.median([x[key] for k,x in enumerate(base) if end!='flat' or k!=j],axis=0);avg=blocks.mean();gate='ok' if avg>=20 else 'below_20dn'
                    if flat.min()<=20:gate='flat_below_floor'
                    row,amp=correction(blocks,flat) if gate=='ok' else ('','')
                    halfspan=50*max(np.diff(np.percentile(x[key],(5,95)))[0] for x in darks)/avg if avg>0 and darks else ''
                    vals=(group,w['scene_rgb'],w['sysfs_bl'],key_light,gross,black,netdiff,grossdiff,long,ph,ns,j+1,key,avg,gate,row,amp,halfspan)
                    out.writerow([round(float(v),5) if isinstance(v,(np.floating,float)) else v for v in vals])


if __name__=='__main__':main()
