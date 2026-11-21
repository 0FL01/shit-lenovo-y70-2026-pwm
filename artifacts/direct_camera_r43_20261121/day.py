"""Range over all replicates, with settings taken from R43's verified video windows."""
import csv
from pathlib import Path
import sys


def load(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))


def main():
    frames,windows=map(load,sys.argv[1:]);out=csv.writer(sys.stdout,lineterminator='\n')
    metrics=('mean_dn','local_plateau_dn','min_dn','depth_pct','michelson_pct','fwhm_raw_rows','dl_us')
    out.writerow(['phase','hwc_id','hz','output','bl','exposure_us','qualified','total',*[k+s for k in metrics for s in ('_min','_max')]])
    for w in windows:
        if w['group']!='day':continue
        r=[f for f in frames if f['phase']==w['phase']];ok=[f for f in r if f['event_status']=='ok'];n=int(w['frames'])
        if len(r)!=n or any(abs(float(f['exposure_us'])*1000-int(w['exposure_ns']))>1 for f in r):raise ValueError(w['phase']+': inconsistent exposure/count')
        row=[w['phase'],w['hwc_id'],w['sf_refresh_hz'],w['hwc_dynamic_range'],w['sysfs_bl'],int(w['exposure_ns'])/1000,len(ok),n]
        for k in metrics:
            v=[float(f[k]) for f in (r if k=='mean_dn' else ok)];row.extend([round(min(v),4),round(max(v),4)] if v else ['',''])
        out.writerow(row)


if __name__=='__main__':main()
