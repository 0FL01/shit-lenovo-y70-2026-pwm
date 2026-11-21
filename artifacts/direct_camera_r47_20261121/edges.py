"""Compare the 312.5-us crossing with same-size no-crossing and repeat-setter controls.

The two archives were acquired separately. Differences are within a bracket,
not frame-by-frame temporal pairings across visits. A/B/C always denote order,
not the side of the threshold. A range is not a confidence interval.
"""
import argparse
import csv
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r46_20261121.width import frame


CASES = [('forward', ('offA','offB','offC')), ('lower', ('offLA','offLB','offLC')),
         ('upper', ('offUA','offUB','offUC')), ('reverse', ('offRA','offRB','offRC')),
         ('sham', ('offLB','offSham'))]


def load(frames, path, states):
    with path.open() as f:
        windows = {w['phase']:w for w in csv.DictReader(f)}
    found, seen = {}, set()
    for state in states:
        phase = f'day_{state}_312'
        w = windows[phase]; n = int(w['frames']); results = []
        if (w['hbm_mode'], int(w['sysfs_bl']), w['panel_dc_pre'], w['pref_post']) not in {
                ('hdr', b, '0', '0') for b in range(15999,16003)}:
            raise ValueError(f'{phase}: not a bound R47 edge')
        for i in range(1,n+1):
            out = frame(frames/f'{phase}__{i}.dng',312.5,seen)
            if out['status']=='ok':
                results.append(out)
        found[state] = (int(w['sysfs_bl']), n, results, w.get('field_status','external_main_cal'))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ('main_frames','main_windows','control_frames','control_windows'):
        ap.add_argument(k, type=Path)
    a = ap.parse_args(); data = load(a.main_frames,a.main_windows,CASES[0][1]); ctrl = load(
        a.control_frames,a.control_windows,sorted({s for _,states in CASES[1:] for s in states}))
    rows = []
    for name, states in CASES:
        groups = [(data if name=='forward' else ctrl)[s] for s in states]
        for metric in ('depth_pct','fwhm_raw_rows'):
            row = dict(bracket=name,metric=metric); mids = []
            for lab,(bl,n,rr,field) in zip('ABC',groups):
                row.update({lab+'_bl':bl,lab+'_n':n,lab+'_qualified':len(rr),lab+'_field':field})
                v = [r[metric] for r in rr]; mids.append(median(v) if v else None)
                if v:
                    row.update({lab+'_min':min(v),lab+'_median':median(v),lab+'_max':max(v)})
            if min(len(rr) for _,_,rr,_ in groups)>=3 and all(g[3] in ('PASS','external_main_cal') for g in groups):
                row['B_minus_reference'] = mids[1]-(mids[0] if len(mids)==2 else (mids[0]+mids[2])/2)
            rows.append(row)
    cols = ['bracket','metric']+[s+'_'+key for s in 'ABC' for key in ('bl','n','qualified','field','min','median','max')]+['B_minus_reference']
    wr = csv.DictWriter(sys.stdout,cols,lineterminator='\n'); wr.writeheader()
    for row in rows:
        wr.writerow({k:format(v,'.9g') if isinstance(v,float) else v for k,v in row.items()})


if __name__=='__main__':
    main()
