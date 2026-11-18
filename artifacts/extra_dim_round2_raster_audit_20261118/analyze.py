"""Read nine trusted stills and surrounding preview results; no device I/O.

For this fixed Extra Dim run only, not an optical waveform or frequency estimator.
"""
import argparse
import csv
import itertools
import json
from pathlib import Path
import numpy as np
from PIL import Image

NAMES=[phase+str(i) for phase in ("off","on","return") for i in (1,2,3)]
VARS=[("R",.96,0,0),("R",.94,0,0),("R",.98,0,0),("R",.96,-3,0),
      ("R",.96,3,0),("R",.96,0,-3),("R",.96,0,3),("G",.96,0,0),("B",.96,0,0)]
PREVIEW={"control.aeLock":"ON","control.aeState":"LOCKED","control.afState":"FOCUSED_LOCKED",
    "control.awbMode":"AUTO","control.awbLock":"OFF","control.captureIntent":"PREVIEW",
    "sensor.exposureTime":"59998320","sensor.sensitivity":"5586","lens.focusDistance":"6.75919294",
    "lens.opticalStabilizationMode":"ON","control.zoomRatio":"2.00000000"}

def read_frame(src,name):
    with Image.open(src/(name+".jpg")) as im:
        e=im.getexif()
        m=e.get_ifd(34665)
        info=(int(e[274]),float(m[33434]),int(m[34855]),float(m[33437]),float(m[37386]),int(m[41987]),int(m[37385]))
        if (im.format,im.size,info)!=("JPEG",(4080,3072),(1,.05999832,5586,1.87,5.56,0,0)):
            raise ValueError("JPEG calibration/EXIF differs")
        img=np.asarray(im.convert("RGB").crop((1120,620,2920,2930)).transpose(
            Image.Transpose.ROTATE_270).resize((550,429),Image.Resampling.LANCZOS))
    retry=0
    times=[]
    for side in ("pre","post"):
        for f in sorted(src.glob(name+"_"+side+"_read*.json")):
            r=json.loads(f.read_text())
            if "sensor.timestamp" not in r:
                retry+=1
                continue
            if any(r.get(k)!=v for k,v in PREVIEW.items()):
                raise ValueError("preview condition changed")
            times.append(int(r["sensor.timestamp"]))
            break
        else:
            raise ValueError("no complete preview metadata")
    if times[1]<=times[0]:
        raise ValueError("preview brackets out of order")
    return img,info,retry

def profile(img,ch,q,dx=0,dy=0):
    chan=img[:,:,"RGB".index(ch)]
    ref=chan[60:135,180:256]
    t=float(np.quantile(ref,q,method="inverted_cdf"))
    if t>=254 or t<=float(np.median(ref)):
        return None,t
    p=(chan[276+dy:322+dy,51+dx:508+dx]>t).mean(axis=0)
    return np.sort(p),t

def grid(red,ref):
    y=int(np.argmax(np.diff(red[34:62,50:480].mean(1))))+34
    borders=[int(np.argmax(abs(np.diff(red[65:110,i:j].mean(0)))))+i for i,j in [(15,45),(513,544)]]
    rho,xs,ys=max((np.corrcoef(ref.ravel(),red[65+y:125+y,183+x:250+x].ravel())[0,1],x,y)
                  for x,y in itertools.product(range(-3,4),repeat=2))
    return [y,*borders,xs,ys,round(float(rho),6)]

def csvout(out,name,header,rows):
    with (out/name).open("x",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(header);w.writerows(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path);p.add_argument("new_dir",type=Path)
    args=p.parse_args()
    data={};rows=[];pairs=[]
    for name in NAMES:
        img,info,retry=read_frame(args.source,name)
        red=img[:,:,0]
        if not data:
            ref=red[65:125,183:250]
        data[name]=img
        s,t=profile(img,*VARS[0])
        if s is None:
            raise ValueError("unresolved primary reference")
        roi=red[276:322,51:508]
        rows.append([name,*info,retry,*grid(red,ref),t,round(float(s.mean()),6),
                     round(float((roi>192).mean()),6),round(float((roi==255).mean()),6)])
    for ch,q,dx,dy in VARS:
        ps={n:profile(img,ch,q,dx,dy)[0] for n,img in data.items()}
        for a,b in itertools.combinations_with_replacement(("off","on","return"),2):
            aa=[ps[n] for n in NAMES if n.startswith(a) and ps[n] is not None]
            bb=[ps[n] for n in NAMES if n.startswith(b) and ps[n] is not None]
            ds=[float(np.abs(x-y).mean()) for x,y in (itertools.combinations(aa,2) if a==b else itertools.product(aa,bb))]
            qs=[round(float(v),6) for v in np.quantile(ds,[0,.5,1])] if ds else ["","",""]
            pairs.append([ch,q,dx,dy,a,b,len(aa),len(bb),len(ds),*qs])
    args.new_dir.mkdir(exist_ok=False)
    csvout(args.new_dir,"frames.csv",["frame","orientation","exposure_s","ISO","F","focal_mm","WB_auto_0","flash","preview_reads_missing_ts","top","left","right","grid_dx","grid_dy","grid_rho","primary_threshold","bright_fraction_relative","bright_fraction_R_gt192","fraction_R_255"],rows)
    csvout(args.new_dir,"pairs.csv",["channel","q","dx","dy","a","b","valid_a","valid_b","n","min","median","max"],pairs)
if __name__=="__main__":
    main()
