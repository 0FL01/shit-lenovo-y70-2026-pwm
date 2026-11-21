#!/usr/bin/env python3
"""R45: python3 -B compare.py frames.csv windows.csv > compare.csv

Use R44 measure.py and R45 windows.py on the same originals. Archived R44
window CSVs also work for replay. Compare only day_{off,on,ret}Low at BL 3593,
in one stock HDR HWC 0/120 Hz clip cycle.
The surface check is at window boundaries. CAL geometry is checked separately.

Each shutter has its own OFF/ON/returned-OFF bracket. Mean DN includes every
frame; depth, Michelson and FWHM include only qualified G1 events. Blank is
unmeasured. Each depth decision cites the original qualified files. As in R44,
an effect needs >=3 qualified in EACH state, <=3 pp OFF-median drift, >=3 pp
ON-median separation from BOTH OFFs and disjoint ON/OFF ranges. The decision
concerns camera depth at that shutter, not physical frequency or emission time.
"""

import argparse
from collections import defaultdict
import csv
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r44_20261121 import compare as r44


SHUTTERS = ('200', '312', '500')  # '312' denotes a 312500 ns exposure
PHASES = {f'day_{state}Low_{shutter}': (state, shutter)
          for state in r44.STATES for shutter in SHUTTERS}
FRAME_FIELDS = ('phase', 'group', 'scene', 'frame_n', 'exposure_us', 'gate', 'event_status', *r44.METRICS)
WINDOW_FIELDS = (*r44.HDR, 'phase', 'frames', 'sysfs_bl', 'dc_label', 'panel_dc_pre',
                 'panel_dc_post', 'pref_pre', 'pref_post', 'sf_refresh_hz', 'sdm_fps',
                 'exposure_ns', 'wake_epoch')


def day_rows(path, fields):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'{path}: expected a regular CSV file')
    for row in r44.read_csv(path, fields):
        p = row['phase']
        if p in PHASES:
            yield row
        elif p.startswith('day_') and 'Low' in p:
            raise ValueError(f'{p}: unexpected low day phase')


def metric_rows(ns, windows, frames):
    """Summarize a verified, ordered OFF/ON/return bracket at one shutter."""
    stats = [r44.summarize(frames[w['phase']], w) for w in windows]
    citations = {}
    for state, w in zip(r44.STATES, windows):
        phase = w['phase']
        indices = sorted(int(f['frame_n']) for f in frames[phase] if f['event_status'] == 'ok')
        citations[state+'_qualified_files'] = ';'.join(f'{phase}__{n}.dng' for n in indices)
    for metric in r44.METRICS:
        w = windows[0]
        row = dict(level='low', exposure_us=ns / 1000, role='exploratory',
                   sysfs_bl=w['sysfs_bl'], hz=w['sf_refresh_hz'], metric=metric)
        ranges = []
        for state, (qualified, total, summary) in zip(r44.STATES, stats):
            row[state+'_qualified'], row[state+'_total'] = qualified, total
            ranges.append(summary[metric])
            for name, value in zip(('min', 'median', 'max'), summary[metric]):
                row[state+'_'+name] = value
        off, on, ret = (r[1] for r in ranges)
        row['on_minus_avg_off_medians'] = on - (off + ret) / 2 if None not in (off, on, ret) else None
        row['depth_decision'] = (r44.depth_decision([s[0] for s in stats], *ranges)
                                 if metric == 'depth_pct' else None)
        row['wake_epoch'] = w['wake_epoch']
        row.update(citations)
        yield row


def compare(frames_csv, windows_csv):
    frames, windows = defaultdict(list), {}
    for f in day_rows(frames_csv, FRAME_FIELDS):
        p = f['phase']
        if (f['group'] != 'day' or f['scene'] != PHASES[p][0]+'Low' or not f['event_status']
                or (f['event_status'] == 'ok' and f['gate'] != 'ok')):
            raise ValueError(f'{p}/{f["frame_n"]}: frame label or event gate disagrees')
        frames[p].append(f)

    epochs = set()
    for w in day_rows(windows_csv, WINDOW_FIELDS):
        p = w['phase']
        if p in windows:
            raise ValueError(f'{p}: duplicate window')
        state, shutter = PHASES[p]
        r44.check_window(w, state, r44.EXPOSURE_NS[shutter])
        if int(w['sysfs_bl']) != 3593:
            raise ValueError(f'{p}: expected BL 3593')
        if 'off_pilot' in w or 'observed_dc_sequence' in w:
            if (w.get('off_pilot'), w.get('observed_dc_sequence')) != ('ALLOW_ON', 'off_on_ret_at_boundaries'):
                raise ValueError(f'{p}: expected a passing R45 pilot and a verified three-state cycle')
        epochs.add(int(w['wake_epoch']))
        windows[p] = w

    for source, found in (('windows', windows), ('frames', frames)):
        missing = PHASES.keys() - found.keys()
        if missing:
            raise ValueError(f'missing {source}: {", ".join(sorted(missing))}')
    if len(epochs) != 1 or min(epochs) <= 0:
        raise ValueError('day windows must share one positive wake epoch')
    # Receipt order matters across shutters too: nine interleaved single-
    # shutter windows cannot establish a single OFF -> ON -> OFF cycle.
    if [PHASES[p][0] for p in windows] != [s for s in r44.STATES for _ in SHUTTERS]:
        raise ValueError('expected all OFF windows, then all ON, then all returned OFF')

    for shutter in SHUTTERS:
        bracket = [windows[f'day_{state}Low_{shutter}'] for state in r44.STATES]
        yield from metric_rows(r44.EXPOSURE_NS[shutter], bracket, frames)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    ap.add_argument('windows_csv', metavar='windows.csv', type=Path)
    args = ap.parse_args()
    try:
        rows = list(compare(args.frames_csv, args.windows_csv))
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
