#!/usr/bin/env python3
"""Independent spatial check on short, white R35 frames; distances are RAW rows, never Hz.

Locate isolated dark events without assuming their period. Select the fine-wave pitch
only on the first three 500 us / BL 3600 frames of each refresh. Use that pitch for
the switch and return even if no wave is visible. Separate low-order trend per light
segment; no extrapolation across a dark event, no extrapolated event at an edge.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'direct_camera_r33_20261120'))
from analyze import read_patch

ROI = (630,1370,540,720)


def intervals(mask):
    ends = np.diff(np.r_[0,mask.astype(int),0])
    return list(zip(np.flatnonzero(ends == 1), np.flatnonzero(ends == -1)))


def profile(path,roi):
    m,g,clip,_ = read_patch(path,roi)
    if clip or g.mean() < 20 or m['iso'] != 6400 or m['focal_length_mm'] != 5.56 or m['exposure_us'] != 500:
        raise ValueError(f'unqualified 500 us capture: {path.name}')
    p = g.mean(axis=1); y = np.arange(len(p)); t = y/len(p)-.5
    # Divide, not subtract: express the residual ripple relative to the local light level.
    p = p / np.polyval(np.polyfit(t,p,2),t)
    smooth = np.convolve(np.pad(p,3,mode='edge'),np.ones(7)/7,'valid')
    centers = []; keep = np.ones(len(y),bool)
    for a,b in intervals(smooth < .65):
        keep[max(0,a-40):min(b+40,len(y))] = False
        if 0 < a and b < len(y) and b-a >= 3:
            centers.append(np.average(2*y[a:b],weights=.65-smooth[a:b]))
    segments = [(a,b) for a,b in intervals(keep) if b-a >= 50]
    if not segments: raise ValueError(f'no light segment in {path.name}')
    chosen = np.concatenate([np.arange(a,b) for a,b in segments]); x=2*y[chosen]; v=p[chosen]
    trend=np.zeros((len(v),3*len(segments))); start=0
    for j,(a,b) in enumerate(segments):
        u=np.linspace(-1,1,b-a);trend[start:start+b-a,3*j:3*j+3]=np.array([u**0,u,u*u]).T;start+=b-a
    q=np.linalg.qr(trend)[0]; z=v-q@(q.T@v)
    def fit(pitch):
        angle=2*np.pi*x[:,None]*np.arange(1,4)/pitch
        X=np.column_stack((np.sin(angle),np.cos(angle))); X-=q@(q.T@X)
        coef=np.linalg.lstsq(X,z,rcond=None)[0];err=z-X@coef
        return err@err,100*np.hypot(coef[0],coef[3]),100*(1-err@err/(z@z))
    return centers,len(v),fit


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('frames',type=Path);ap.add_argument('--long-strip',action='store_true',help='second interior strip: y605:1475,x540:640 in Bayer cells');args=ap.parse_args()
    rx=re.compile(r'h(90|120|144)_b(3600|3601)_t500(_ret)?__(\d+)\.dng')
    data={}
    for path in sorted(args.frames.glob('*__*.dng')):
        m=rx.fullmatch(path.name)
        if m: data[(int(m[1]),int(m[2]),bool(m[3]),int(m[4]))]=profile(path,(605,1475,540,640) if args.long_strip else ROI)
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow(('refresh','sysfs_bl','return','frame','kept_bayer_rows','independent_pitch_raw','locked_pitch_raw','fundamental_semiamp_pct','three_harmonic_r2_pct','complete_dark_centers','dark_spacing_raw','dark_over_locked_pitch'))
    for hz in sorted({k[0] for k in data}):
        pitches={}
        for key,(_,_,fit) in data.items():
            if key[:3] != (hz,3600,False):continue
            # Both fixed 720 and 6x refresh have wide margin within this search band.
            coarse=min(np.arange(105,315.1,1), key=lambda p:fit(p)[0]);pitches[key]=min(np.arange(coarse-1,coarse+1.01,.05), key=lambda p:fit(p)[0])
        if len(pitches)!=3:raise ValueError(f'missing calibration triplet at {hz}')
        pitch=np.median(list(pitches.values()))
        for key,(centers,kept,fit) in sorted(data.items()):
            if key[0]!=hz:continue
            _,amp,r2=fit(pitch);ds=float(np.median(np.diff(centers))) if len(centers)>=2 else None
            out.writerow((hz,key[1],int(key[2]),key[3],kept,round(pitches[key],3) if key in pitches else '',round(pitch,3),round(amp,4),round(r2,3),len(centers),'' if ds is None else round(ds,2),'' if ds is None else round(ds/pitch,3)))


if __name__=='__main__': main()
