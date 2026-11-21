"""Summarize all replicates on each field's preselected CFA site, not its deepest site."""
import csv
from pathlib import Path
import re
import sys


def main():
    path=Path(sys.argv[1]);primary={'white':'G1','whiteRet':'G1','red':'R','green':'G1','blue':'B','yellow':'G1'}
    with path.open() as f:rows=list(csv.DictReader(f))
    cols=('mean_dn','row_notch_pct','camera_block_contrast_pct','notch_fwhm_raw_rows','run_spacing_raw_rows')
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow(['exposure_us','scene','site','n','qualified',*[k+s for k in cols for s in ('_min','_max')],'dark_halfspan_pct_max'])
    for ns in sorted({int(m[1]) for z in rows if (m:=re.fullmatch(r'b(\d+)_white',z['phase']))}):
        for name,site in primary.items():
            rr=[r for r in rows if r['phase']==f'b{ns}_{name}' and r['site']==site];bg=[r for r in rows if r['phase']==f'b{ns}_black' and r['site']==site];valid=[r for r in rr if r['gate']=='ok']
            if len(rr)!=3 or len(bg)!=2:raise ValueError(f'incomplete group {ns}/{name}')
            vals=[]
            for k in cols:
                v=[float(r[k]) for r in (rr if k=='mean_dn' else valid) if r[k]];vals.extend([round(min(v),4),round(max(v),4)] if v else ['',''])
            noise=50*max(float(r['block_p95_dn'])-float(r['block_p05_dn']) for r in bg)/min(float(r['mean_dn']) for r in rr)
            out.writerow((ns/1000,name,site,len(rr),len(valid),*vals,round(noise,4)))


if __name__=='__main__':main()
