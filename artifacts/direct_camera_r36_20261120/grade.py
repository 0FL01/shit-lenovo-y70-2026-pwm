"""Summarize full-field R36 evening matching and two independent exposure tests."""
import argparse
import csv
from pathlib import Path
from statistics import median
import sys


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--dir',type=Path,default=Path(__file__).resolve().parent)
    cli.add_argument('--groups',nargs='+',default=('ref','hi','refret','hiret'));a=cli.parse_args();d=a.dir
    with (d/'frames.csv').open() as f:frames=list(csv.DictReader(f))
    with (d/'windows.csv').open() as f:windows={x['phase']:x for x in csv.DictReader(f)}
    def group(ph):return [x for x in frames if x['phase']==ph]
    def level(ph):return median(float(x['green_mean_dn']) for x in group(ph))
    base=level('ref_flat');delta=base-level('ref_black')
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('group patch DBV gross_dn black_dn net_dn net_vs_ref_pct gross_vs_ref_pct short_exposure_us frames row_dip_min_pct row_dip_max_pct block_min_pct block_max_pct'.split())
    scene='scene' if 'scene' in windows['ref_flat'] else 'scene_rgb'
    for case in a.groups:
        w=windows[case+'_flat'];gross=level(case+'_flat');bg=level(case+'_black')
        for suffix in ('short','other'):
            ph=case+'_'+suffix;rr=group(ph)
            if not rr or not all(x['flat_status']=='ok' and x['flat_ref_phase']==case+'_flat' for x in rr):raise ValueError('unusable short frame')
            if not (windows[ph][scene]==w[scene] and windows[ph]['DBV']==w['DBV'] and windows[case+'_black'][scene]=='000000'):raise ValueError('scene/brightness not matched')
            vals=[[float(x[k]) for x in rr] for k in ('flat_row_p01_dip_pct','flat_block_contrast_pct')]
            out.writerow([case,w[scene],w['DBV'],*(round(x,4) for x in (gross,bg,gross-bg,100*((gross-bg)/delta-1),100*(gross/base-1))),rr[0]['exposure_us'],len(rr),*(round(x,4) for v in vals for x in (min(v),max(v)))])


if __name__=='__main__':main()
