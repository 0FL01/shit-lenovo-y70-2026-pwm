"""Apply the existing R43 blur/spacing gates separately on either side of APL; do not use CAL as DAY."""
import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.timing import FIELDS, US, analyze


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('frames', type=Path)
    p = ap.parse_args().frames
    shutters = {k: US[k] for k in ('125','200','312')}
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n'); out.writeheader()
    for row in analyze(p, dict.fromkeys(('offA','offB','offC'), shutters)):
        out.writerow({k:format(v,'.9g') if isinstance(v,float) else v for k,v in row.items()})


if __name__=='__main__':
    main()
