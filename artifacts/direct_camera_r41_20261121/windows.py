#!/usr/bin/env python3
"""Bind R41 optical windows to scene receipts, private SF snapshots and measured DNGs.

Usage: python windows.py ARCHIVE CHANNELS_CSV LOG [LOG ...] > windows.csv
Logs are acquisition transcripts in chronological order, relative to ARCHIVE or
absolute. active_0x8e labels the owner recipe session: these optical windows
have no native panel readback. A standalone pilot is geometry only.
"""

import argparse
import csv
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'direct_camera_r35_20261120'))
from evidence import mode, need


PHASE = r'[A-Za-z0-9_]+'
POS = r'[1-9][0-9]*'
HEX = r'[0-9a-f]{6}'
FRAME = re.compile(rf'({PHASE})__({POS})')
STATE = rf'({PHASE}) BL=([0-9]+) hwcId=0 ns=({POS}) rgb=({HEX}) wake=([0-9]+)'
SITES = {'R', 'G1', 'B', 'G2'}
COLUMNS = ('phase phase_ordinal profile scene_rgb sysfs_bl hwc_both refresh_both group_both '
           'sf_rgb_both exposure_ns frames wake_epoch native_readbacks').split()


def inventory(directory):
    sizes, identities = {}, set()
    for path in directory.iterdir():
        need(not path.name.endswith('.partial'), 'unfinished frame transfer')
        if path.suffix.lower() != '.dng':
            continue
        match = FRAME.fullmatch(path.stem)
        need(match and path.suffix == '.dng' and path.is_file(), 'invalid DNG filename')
        st = path.stat()
        identity = st.st_dev, st.st_ino
        need(st.st_size > 0 and identity not in identities, 'empty or duplicate DNG')
        identities.add(identity)
        sizes[match[1], int(match[2])] = st.st_size
    phases = sorted({ph for ph, n in sizes})
    return sizes, {ph: i for i, ph in enumerate(phases, 1)}


def exposures(path, sizes, ordinals):
    by_frame, sites = {}, {}
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        required = {'phase', 'frame_n', 'site', 'exposure_us', 'iso', 'focal_mm'}
        need(len(set(fields)) == len(fields), 'duplicate channels.csv column')
        missing = required.difference(fields)
        need(not missing, 'channels.csv missing column(s): ' + ', '.join(sorted(missing)))
        for row in reader:
            ph = row['phase']
            need(None not in row and None not in row.values() and re.fullmatch(POS, row['frame_n']),
                 f'channels.csv line {reader.line_num}: malformed frame row')
            key = ph, int(row['frame_n'])
            need(key in sizes, f'{ph}: unmatched channels.csv frame')
            if 'phase_ordinal' in fields:
                need(row['phase_ordinal'] == str(ordinals[ph]), f'{ph}: incorrect phase_ordinal')
            site = row['site']
            found = sites.setdefault(key, set())
            need(site in SITES and site not in found, f'{ph}/{key[1]}: unexpected or duplicate Bayer site')
            found.add(site)
            # measure.py has already checked native geometry and GBRG before
            # emitting these four rows; check the exported camera tags here.
            need(row['iso'] == '6400' and float(row['focal_mm']) == 5.56, f'{ph}: unexpected DNG ISO/lens')
            ns = float(row['exposure_us']) * 1000
            need(math.isfinite(ns) and ns > 0, f'{ph}: invalid DNG exposure')
            need(by_frame.setdefault(key, ns) == ns, f'{ph}/{key[1]}: inconsistent site exposures')
    need(by_frame.keys() == sizes.keys(), 'DNG inventory and channels.csv differ')
    need(all(group == SITES for group in sites.values()), 'incomplete Bayer sites in channels.csv')
    return by_frame


def snapshot(path):
    summary = mode(path, 120)
    # R35's published RGB summary contains only the three rounded diagonal
    # gains. Compare all 16 SF coefficients, including channel mixing/offsets.
    matrices = re.findall(r'colorTransformMatrix=\[(\[.*?\])\]', path.read_text())
    values = {tuple(map(float, re.findall(r'-?\d+\.\d+', m))) for m in matrices}
    need(len(values) == 1 and len(next(iter(values))) == 16, f'{path.name}: ambiguous SF matrix')
    return summary, values.pop()


def events(path):
    with path.open() as stream:
        for raw in stream:
            line = raw.strip()
            words = line.split(maxsplit=1)
            if words and words[0] in {'scene', 'PRE', 'frame', 'POST'}:
                yield line
            elif line == 'no new DNG':
                raise ValueError('failed capture in acquisition transcript')


def bind(archive, channels_csv, logs):
    sizes, ordinals = inventory(archive / 'frames')
    durations = exposures(channels_csv, sizes, ordinals)
    rows, consumed, seen = [], set(), set()
    for log in logs:
        stream = events(archive / log)
        rgb = None
        for line in stream:
            if line.startswith('scene '):
                m = re.fullmatch(rf'scene ({HEX}) (.+)', line)
                need(m, 'invalid scene receipt')
                rgb = m[1]
                components = bytes.fromhex(rgb)
                need(m[2] == str(tuple((x, x) for x in components)), 'scene extrema disagree with RGB')
                continue
            if m := re.fullmatch(rf'frame pilot__1 ({POS})', line):
                key = 'pilot', 1
                need(key not in consumed and sizes.get(key) == int(m[1]), 'invalid standalone pilot receipt')
                consumed.add(key)
                rgb = None
                continue
            pre = re.fullmatch('PRE ' + STATE, line)
            need(pre, 'expected PRE after scene or standalone pilot')
            ph, bl, ns, declared, wake = pre.groups()
            need(ph not in seen and ph != 'pilot' and rgb == declared, f'{ph}: duplicate phase or missing/mismatched scene')
            count = 0
            for line in stream:
                frame = re.fullmatch(rf'frame {FRAME.pattern} ({POS})', line)
                if not frame:
                    break
                count += 1
                key = ph, count
                need(frame.group(1, 2) == (ph, str(count)) and sizes.get(key) == int(frame[3]),
                     f'{ph}: frame order, ordinal or file size mismatch')
                need(abs(durations[key] - int(ns)) <= 1, f'{ph}: DNG exposure mismatch at frame {count}')
                consumed.add(key)
            post = re.fullmatch('POST ' + STATE + rf' count=({POS})', line)
            need(count and post and post.groups()[:-1] == pre.groups() and int(post[6]) == count,
                 f'{ph}: missing/mismatched POST, wake or frame count')
            sf, matrix = snapshot(archive / f'{ph}-pre.sf')
            need(snapshot(archive / f'{ph}-post.sf') == (sf, matrix), f'{ph}: SF state changed')
            seen.add(ph)
            rows.append(dict(zip(COLUMNS, (ph, ordinals[ph], 'active_0x8e', rgb, bl, *sf,
                                           ns, count, wake, 'none'))))
            rgb = None

    if ('pilot', 1) in sizes:
        consumed.add(('pilot', 1))
        rows.append(dict(phase='pilot', phase_ordinal=ordinals['pilot'], profile='geometry only',
                         frames=1, exposure_ns=round(durations['pilot', 1]), native_readbacks='none'))
    need(seen and consumed == sizes.keys(), 'unbound DNG or missing optical window')
    for side in ('pre', 'post'):
        suffix = f'-{side}.sf'
        need({p.name[:-len(suffix)] for p in archive.glob('*' + suffix)} == seen,
             f'unbound {side} SF snapshot')
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', type=Path)
    ap.add_argument('channels_csv', type=Path)
    ap.add_argument('logs', nargs='+')
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.channels_csv, args.logs)
    except OSError as exc:
        ap.error(exc.strerror)  # keep private paths out of published diagnostics
    except (ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=COLUMNS, lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
