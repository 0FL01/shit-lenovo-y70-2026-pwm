"""Independent effective phase scale from blurring an isolated deep stripe.

For a stationary profile viewed at constant effective phase gradient, a short
capture convolved by the long box and a long capture by the short box should
match (boxes commute). No sinusoid, panel-counter units or rolling-skew tag.
This is NOT a calibration of the camera sensor alone: the photographed panel
scans too. Applied only above the stock threshold where fine ripple is weak.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct_camera_r33_20261120'))
from analyze import read_patch

ROI=(630,1370,540,720)


def event(path):
    m,g,clip,_=read_patch(path,ROI);p=g.mean(1);x=np.arange(len(p));t=m['exposure_us']
    if g.mean()<20 or clip or m['iso']!=6400 or m['focal_length_mm']!=5.56:return None
    p=p/np.polyval(np.polyfit(x,p,2),x)
    # Peak deficit averaged over a neighbourhood; neither the darkest raw pixel
    # nor the edge of a clipped event is a reliable fiducial on a long exposure.
    sm=np.convolve(np.pad(p,10,mode='edge'),np.ones(21)/21,'valid');lag=90
    deficit=(sm[:-2*lag]+sm[2*lag:])/2-sm[lag:-lag]
    peaks=[i+lag for i in range(1,len(deficit)-1) if deficit[i]>=deficit[i-1] and deficit[i]>deficit[i+1] and deficit[i]>.10]
    peaks=[i for i in peaks if 145<=i<len(p)-145]
    if not peaks:return None
    i=max(peaks,key=lambda y:deficit[y-lag]);seg=p[i-145:i+146]
    if min(np.mean(seg[:15]),np.mean(seg[-15:]))-np.min(seg[100:191])<.12:return None
    return t,seg


def box(profile,width):
    # Fractional end cells. Width is in Bayer rows, each two raw rows.
    r=int(np.ceil((width+1)/2));x=np.arange(-r,r+1)
    w=np.maximum(0,np.minimum(x+.5,width/2)-np.maximum(x-.5,-width/2))
    return np.convolve(np.pad(profile,r,mode='edge'),w/w.sum(),'valid')


def cost(a,b,s):
    t1,u=a;t2,v=b
    u=box(u,t2/(2*s));v=box(v,t1/(2*s))
    # Fit translation, constant, gain and a small local illumination slope. The
    # loss is normalized by observed feature energy, so blurring away all contrast
    # is not a useful minimum. Align by residual shape, not by location of minimum.
    offsets=np.arange(-38,39);x=np.arange(68,223);w=v[x];drift=np.linspace(-1,1,len(x));Q=np.array([drift**0,drift]);Q=np.linalg.qr(Q.T)[0];w=w-Q@(Q.T@w)
    u=u[x[:,None]+offsets];u-=Q@(Q.T@u);corr=(w@u)/np.sqrt((w@w)*np.sum(u*u,axis=0));return 1-np.max(corr)**2


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('--archive-r33',action='store_true');a=ap.parse_args()
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('refresh short_us long_us short_n long_n pairs effective_us_per_raw_row pair_min pair_max median_shape_r2_pct search_edge'.split())
    for hz in (90,120,144):
        if a.archive_r33:
            phases={120:('f01_125day120','g01_500day120'),144:('f02_125day144','g02_500day144')}.get(hz);fs=[] if phases is None else sum((list(a.frames.glob(p+'__*.dng')) for p in phases),[])
        else:fs=[f for f in a.frames.glob('*__*.dng') if re.fullmatch(rf'(?:h|link){hz}_b3601_t(?:312|500|1250)__\d+',f.stem)]
        groups={}
        for f in sorted(fs):
            z=event(f)
            if z:groups.setdefault(z[0],[]).append(z)
        for t1 in sorted(groups):
            for t2 in sorted(groups):
                if t2<=t1:continue
                scales=np.arange(3.,14.01,.1); pairs=[(u,v) for u in groups[t1] for v in groups[t2]]
                curves=np.array([[cost(u,v,s) for s in scales] for u,v in pairs]);curve=np.median(curves,axis=0);j=np.argmin(curve);opt=scales[np.argmin(curves,axis=1)]
                out.writerow((hz,t1,t2,len(groups[t1]),len(groups[t2]),len(pairs),round(scales[j],2),round(min(opt),2),round(max(opt),2),round(100*(1-curve[j]),2),int(j in (0,len(scales)-1))))


if __name__=='__main__':main()
