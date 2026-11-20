#!/usr/bin/env python3
"""Bind R37 acquisition logs to native, SurfaceFlinger and R34 measure.py evidence.

Usage: python windows.py ARCHIVE FRAMES_CSV [LOG ...] > windows.csv
LOGs are complete acquisition transcripts in chronological order (default: slow.log).
snaps.log and windows.log are tee copies, not acquisition transcripts.
"""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
import math
from pathlib import Path
import re
import sys
from typing import NamedTuple


spec = spec_from_file_location('r33_windows', Path(__file__).resolve().parents[1] /
                               'direct_camera_r33_20261120/windows.py')
r33 = module_from_spec(spec)
spec.loader.exec_module(r33)


class Policy(NamedTuple):
    hw: str
    bl: str
    dc: str
    ns: int
    count: int
    rgb: str


HZ = {'0': 120, '6': 30, '7': 24}
SWEEP = {'a120': '0', 'b30': '6', 'c24': '7', 'd30': '6', 'e120': '0'}
POLICY = {ph: Policy(hw, '3601', '0', 312500, {'0': 3, '6': 6, '7': 8}[hw], 'ffffff')
          for ph, hw in SWEEP.items()}
for step, dc in [('pre', '0'), ('off_on', '1'), ('on_off', '0')]:
    for suffix, ns, n, rgb in [('black', 25000000, 3, '000000'), ('flat', 25000000, 3, 'ffffff'),
                               ('short', 4000000, 4, 'ffffff')]:
        POLICY[f'{step}_{suffix}'] = Policy('0', '512', dc, ns, n, rgb)

SNAP = re.compile(r'SNAP ([a-z0-9_]+) (pre|post) hw=([067]) R37_OK bl=(\d+) dc=([01]) '
                  r'epoch=(\d+) A9=([0-9a-f]{2}) D9=([0-9a-f]{2}) R80=([0-9a-f]{2}) '
                  r'F81=([0-9a-f]{2}) C1=([0-9a-f]{6}) DBV=([0-9a-f]{4}) page=(0) esd=(reg_read)')
FRAME = re.compile(r'frame ([a-z0-9_]+)__([1-9][0-9]*) ([1-9][0-9]*)')
CAMERA = dict(width='4080', height='3072', orientation='1', cfa='GBRG', iso='6400', focal_mm='5.56')
COLUMNS = ('phase phase_ordinal role scene_rgb sysfs_bl dc hwc_both refresh_both group_both '
           'sf_rgb_both exposure_ns frames wake_epoch A9 D9 R80 F81 C1 DBV page esd').split()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def inventory(directory, csv_path, policy=POLICY):
    sizes, files = {}, set()
    for path in directory.iterdir():
        need(not path.name.endswith('.partial'), 'unfinished frame transfer')
        if path.suffix.lower() != '.dng':
            continue
        m = re.fullmatch(r'([a-z0-9_]+)__([1-9][0-9]*)\.dng', path.name)
        need(m and (m[1] in policy or m[1] == 'pilot') and path.is_file(), 'unexpected frame file')
        st = path.stat()
        identity = st.st_dev, st.st_ino
        need(identity not in files and st.st_size > 1000000, 'duplicate or incomplete frame file')
        files.add(identity)
        sizes[m[1], int(m[2])] = st.st_size

    ordinals = {ph: i for i, ph in enumerate(sorted({k[0] for k in sizes}), 1)}  # measure.py
    durations = {}
    with csv_path.open(newline='') as stream:
        rows = csv.DictReader(stream)
        fields = rows.fieldnames or []
        need(len(fields) == len(set(fields)) and
             {'phase', 'phase_ordinal', 'frame_n', 'exposure_us', *CAMERA} <= set(fields),
             'missing or ambiguous measure.py columns')
        for r in rows:
            ph = r['phase']
            need(None not in r and ph in ordinals and r['phase_ordinal'] == str(ordinals[ph]) and
                 re.fullmatch(r'[1-9][0-9]*', r['frame_n'] or ''), 'incorrect DNG phase or ordinal')
            key = ph, int(r['frame_n'])
            need(key in sizes and key not in durations and all(r[k] == v for k, v in CAMERA.items()),
                 f'{ph}: duplicate, missing or mismatched DNG')
            try:
                ns = 1000 * float(r['exposure_us'])
            except (ValueError, TypeError):
                raise ValueError(f'{ph}: invalid DNG exposure') from None
            need(math.isfinite(ns) and ns > 0 and (ph == 'pilot' or abs(ns - policy[ph].ns) <= 1),
                 f'{ph}: DNG exposure mismatch')
            durations[key] = ns
    need(sizes.keys() == durations.keys(), 'unmeasured DNG files')
    return sizes, ordinals, durations


def mode(path, hw):
    actual, matrix = r33.sf(path)
    modes = re.findall(r'activeMode=\{([^}\n]+)\}', path.read_text())
    rates = set()
    for record in modes:
        rate = re.search(r'\bvsyncRate=([0-9]+(?:\.[0-9]+)?) Hz,', record)
        need(rate and re.search(rf'\bhwcId={hw},', record) and re.search(r'\bgroup=0x3(?:,|$)', record),
             'unexpected active SF mode/group')
        rates.add(float(rate[1]))
    need(actual == hw and len(rates) == 1 and abs(next(iter(rates)) - HZ[hw]) <= .05,
         'ambiguous or wrong SF refresh')
    return rates.pop(), matrix


def native(match, hw, bl, dc):
    # R37_OK dc certifies both provider GET and panelDC; the register core is independent.
    need(match and match.group(3, 4, 5) == (hw, bl, dc), 'native HWC/brightness/DC mismatch')
    core = ('0e', '0e', '50') if dc == '0' else ('8e', '8e', '90')
    need(match.group(7, 8, 9) == core and int(match[12], 16) == int(bl), 'native core or panel DBV mismatch')


def scene(line):
    m = re.match(r'scene (([0-9a-f]{2})\2\2) ', line)
    need(m, 'invalid neutral scene code')
    v = int(m[2], 16)
    need(line == f'scene {m[1]} {((v, v),) * 3}', 'scene RGB extrema disagree with gray code')
    return m[1]


def events(path):
    with path.open() as stream:
        for raw in stream:
            line = raw.strip()
            fields = line.split(maxsplit=1)
            if (fields and fields[0] in {'SNAP', 'WINDOW', 'frame', 'scene', 'NOT_LANDED'}) or line == 'no new DNG':
                yield line


def bind(archive, frames_csv, logs, policy=POLICY):
    sizes, ordinals, durations = inventory(archive / 'frames', frames_csv, policy)
    out, seen, skipped, captured = [], set(), set(), set()
    mirrors = {'snaps.log': [], 'windows.log': []}
    for log in logs:
        stream = events(archive / log)
        rgb = seed = None
        restored = started = False
        for line in stream:
            if line.startswith('scene '):
                rgb = scene(line)
                continue
            if m := re.fullmatch(r'NOT_LANDED ([a-z0-9]+) hwcId=(\d+)', line):
                ph = m[1]
                need(ph in policy and ph in SWEEP and m[2] != SWEEP[ph] and ph not in ordinals and
                     ph not in skipped and not restored, 'invalid NOT_LANDED or files for skipped phase')
                skipped.add(ph)
                started = True
                continue
            if m := FRAME.fullmatch(line):
                # A separately recorded geometry pilot has no native window.
                key = ('pilot', 1)
                need(m.group(1, 2) == ('pilot', '1') and key not in captured and
                     sizes.get(key) == int(m[3]), 'frame outside native window')
                captured.add(key)
                continue

            pre = SNAP.fullmatch(line)
            need(pre and not restored, 'unexpected event; expected native SNAP pre')
            ph, side = pre.group(1, 2)
            mirrors['snaps.log'].append(line)
            if ph in ('init', 'restored'):
                native(pre, '0', '3601', '0')
                mode(archive / f'{ph}-{side}.sf', '0')
                if ph == 'init':
                    need(side == 'pre' and seed is None and not started and pre[10] in ('06', '10'),
                         'invalid initial stock snapshot')
                    seed = pre[10]
                else:
                    need(side == 'post' and seed == pre[10], 'stock F81 was not restored')
                    restored = True
                continue

            need(ph in policy and ph not in seen and ph not in skipped and side == 'pre',
                 'unknown, duplicate or unordered window start')
            started = True
            p = policy[ph]
            native(pre, p.hw, p.bl, p.dc)
            need(rgb == p.rgb, f'{ph}: missing or unexpected measured scene')
            rate, matrix = mode(archive / f'{ph}-pre.sf', p.hw)
            for i in range(1, p.count + 1):
                frame = FRAME.fullmatch(next(stream, ''))
                need(frame and frame.group(1, 2) == (ph, str(i)) and sizes.get((ph, i)) == int(frame[3]),
                     f'{ph}: incorrect frame order, status or size')
                captured.add((ph, i))
            post_line = next(stream, '')
            post = SNAP.fullmatch(post_line)
            need(post and post.group(1, 2) == (ph, 'post') and pre.groups()[2:] == post.groups()[2:],
                 f'{ph}: missing post or changed native state')
            mirrors['snaps.log'].append(post_line)
            need(mode(archive / f'{ph}-post.sf', p.hw) == (rate, matrix), f'{ph}: SF changed')
            window = next(stream, '')
            need(window == f'WINDOW {ph} {p.hw} {p.bl} {p.dc} {p.ns} {p.count} {rgb}',
                 f'{ph}: missing WINDOW or policy/scene mismatch')
            mirrors['windows.log'].append(window)
            seen.add(ph)
            out.append((ph, ordinals[ph], 'stock', rgb, p.bl, p.dc, p.hw, rate, '0x3', matrix,
                        p.ns, p.count, *pre.groups()[5:]))
        need(seed is None or restored, 'missing restored stock snapshot')

    for name, receipts in mirrors.items():
        path = archive / name
        if path.exists():
            need(path.read_text().splitlines() == receipts, f'{name}: tee receipts differ from acquisition logs')
    if ('pilot', 1) in sizes:
        captured.add(('pilot', 1))
        out.append(('pilot', ordinals['pilot'], 'geometry only', *([''] * 7), durations['pilot', 1], 1,
                    *([''] * 9)))
    need(seen and sizes.keys() == captured, 'missing measured window or unbound frames')
    return out


def main(binder=bind, default_log='slow.log', description=__doc__):
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', type=Path)
    ap.add_argument('frames_csv', type=Path)
    ap.add_argument('logs', nargs='*', default=[default_log])
    args = ap.parse_args()
    try:
        rows = binder(args.archive, args.frames_csv, args.logs)
    except OSError as exc:
        ap.error(exc.strerror)  # no private paths in diagnostics
    except (ValueError, csv.Error) as exc:
        ap.error(str(exc))
    writer = csv.writer(sys.stdout, lineterminator='\n')
    writer.writerow(COLUMNS)
    writer.writerows(rows)


if __name__ == '__main__':
    main()
