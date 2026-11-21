"""Compare requested policy, the movie's layer vote and the actual physical mode at R46 probes."""
import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121.windows import snapshot


def probes(archive):
    log = (archive/'acquisition.log').read_text()
    wake = int((archive/'epoch').read_text())
    for name, hw, hz, dc in re.findall(r'^PROBE (\w+) hw=(\d+) hz=(\d+) BL=3593 dc=([01])$', log, re.M):
        def read(suffix):
            return (archive/f'{name}.{suffix}').read_text()
        state, _ = snapshot(archive, name, 'hdr', 3593, int(hw), int(hz), wake, 'on' if dc=='1' else 'off')
        sf, display = read('sf'), read('display')
        lo, hi = read('request').split()
        policy = re.search(r'displayManagerPolicy=\{defaultModeId=(\d+), allowGroupSwitching=(true|false), primaryRanges=\{physical=\[([\d.]+) Hz, ([\d.]+) Hz\]', sf)
        vote = re.search(r'SurfaceView\[[^\n]*?VideoPlayerActivity\]\(BLAST\)#\d+\s*\n[^\n]*?\|\s*([\d.]+)\s+(ExactOrMultiple)\s+(OnlySeamless|Always)', sf)
        opt = re.search(r'PRIORITY_SYSTEM_OPTIMIZED_REFRESH_RATE -> .*?mMinRefreshRate=([\d.]+), mMaxRefreshRate=([\d.]+)', display)
        yield dict(probe=name, request_min=lo, request_peak=hi, user_preferred=read('preferred').strip().split(': ')[-1],
                   sf_base=policy[1] if policy else '', group_switch=policy[2] if policy else '',
                   primary_hz=':'.join(policy.groups()[2:]) if policy else '',
                   optimized_hz=':'.join(opt.groups()) if opt else '', layer_vote=' '.join(vote.groups()) if vote else '',
                   hwc_id=hw, actual_hz=hz, bl=state['sysfs_bl'], hdr_sdr_ratio=state['hdr_sdr_ratio'],
                   hbm=state['hbm_mode'], panel_dc=state['panel_dc'], provider=state['pref'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('archive', type=Path)
    rows = list(probes(ap.parse_args().archive))
    if not rows:
        ap.error('no qualified R46 probe receipts')
    out = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n'); out.writeheader(); out.writerows(rows)
