"""Verify the sampled Android brightness settings against the same genuine HDR surface."""
import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.state import summarize
from direct_camera_r44_20261121.windows import snapshot


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    a = ap.parse_args().archive
    matches = re.findall(r'^LOW_DRIVE sample=(\d+) float=([0-9.]+) BL=(\d+)$',
                         (a/'acquisition.log').read_text(), re.M)
    if not matches or len({m[0] for m in matches}) != len(matches):
        raise ValueError('no unique completed brightness probes')
    wake = int((a/'epoch').read_text())
    rows, surfaces = [], set()
    for sample, setting, b in matches:
        stem = f'drive{sample}'
        edge, surface = snapshot(a, stem, 'hdr', int(b), 0, 120, wake, 'off')
        surfaces.add(surface)
        s = summarize((a/f'{stem}.sf').read_text(), (a/f'{stem}.display').read_text())
        rows.append((sample, setting, b, edge['hdr_mode'], edge['hbm_mode'], edge['hdr_sdr_ratio'],
                     s['framework_actual_sdr_backlight'], edge['sf_refresh_hz']))
    if len(surfaces) != 1:
        raise ValueError('video surface changed between brightness samples')
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow('sample android_request sysfs_bl hdr_modifier hbm_mode hdr_sdr_ratio actual_sdr_backlight hz'.split())
    w.writerows(rows)


if __name__ == '__main__':
    main()
