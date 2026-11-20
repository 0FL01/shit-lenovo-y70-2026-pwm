"""Plot the fitted exposure response; independently score the new 400/625 us windows."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np
from PIL import Image,ImageDraw


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('fit',type=Path);ap.add_argument('carrier',type=Path);ap.add_argument('png',type=Path);a=ap.parse_args()
    with a.fit.open() as f:rows=[r for r in csv.DictReader(f) if r['bl']=='3600' and r['mask']=='notch_excluded']
    with a.carrier.open() as f:hold=[r for r in csv.DictReader(f) if r['role']=='external' and r['bl']=='3600' and r['status']=='ok' and r['masked_amp_frac'] and float(r['exposure_us']) in (400,625)]
    rates=sorted({int(r['rate_hz']) for r in rows if r['kind']=='group'});models=[('fixed_720','#165996'),('6x_refresh','#d07800'),('best_100_10000','#459753'),('best_gt2000','#8e5ea2')];image=Image.new('RGB',(790,50+156*len(rates)+26),'white');draw=ImageDraw.Draw(image)
    draw.text((35,4),'Fine component outside deep stripe: semi-amplitude (% of mean) vs DNG exposure (us)',fill='black')
    draw.text((35,20),'Black: measured; red: held-out 400/625 us. Blue: fixed 720 Hz; orange: 6 x refresh.',fill='black');out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('refresh frames exposure_us observed_min_pct observed_median_pct observed_max_pct model fitted_hz prediction_pct residual_pp'.split())
    for i,hz in enumerate(rates):
        group=[r for r in rows if r['rate_hz']==str(hz) and r['kind']=='group'];held={t:[100*float(r['masked_amp_frac']) for r in hold if r['rate_hz']==str(hz) and float(r['exposure_us'])==t] for t in (400,625)}
        params={r['model']:(float(r['model_hz']),float(r['a0_frac'])) for r in rows if r['scope']=='per_rate' and r['rate_hz']==str(hz) and r['kind']=='fit' and r['status']=='ok'}
        y0=46+i*156;cap=5*max(5,np.ceil(max(float(r['max_amp_frac'])*100 for r in group)/5));x=lambda t:55+(t/2600)*700;y=lambda amp:y0+124-110*amp/cap
        draw.text((5,y0-3),f'{hz} Hz',fill='black');
        for v in (0,cap/2,cap):draw.line((55,y(v),755,y(v)),fill='#cbd3db');draw.text((20,y(v)-5),f'{v:g}',fill='black')
        for t in (0,500,1000,1500,2000,2500):draw.text((x(t)-7,y(0)+3),str(t),fill='black')
        for name,col in models:
            freq,amp=params[name];predict=lambda us:100*amp*abs(np.sinc(freq*us/1e6))
            if name in ('fixed_720','6x_refresh'):
                times=np.arange(300,2521,10);draw.line([(x(t),y(predict(t))) for t in times],fill=col,width=2)
            for t,obs in held.items():
                if obs:out.writerow((hz,len(obs),t,round(min(obs),3),round(np.median(obs),3),round(max(obs),3),name,int(freq),round(predict(t),3),round(np.median(obs)-predict(t),3)))
        for r in group:
            xx=x(float(r['exposure_us']));yy=y(float(r['amp_frac'])*100);draw.line((xx,y(100*float(r['min_amp_frac'])),xx,y(100*float(r['max_amp_frac']))),fill='black');draw.ellipse((xx-3,yy-3,xx+3,yy+3),fill='black')
        for t,obs in held.items():
            if obs:
                xx=x(t);yy=y(np.median(obs));draw.ellipse((xx-3,yy-3,xx+3,yy+3),fill='#b01f32')
    image.save(a.png)


if __name__=='__main__':main()
