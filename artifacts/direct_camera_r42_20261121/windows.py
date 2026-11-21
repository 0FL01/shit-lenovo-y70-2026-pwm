#!/usr/bin/env python3
"""Bind R42 acquisition receipts to original target PNGs, SF dumps and A001 DNGs.

python3 -B windows.py ARCHIVE [--logs cal.log [day.log ...]] > windows.csv
Default: require all three logs and account for the entire frame/window inventory.
Explicit subset: still check the complete inventory of every selected phase.
The preflight session status and window wake receipts are not panel readbacks.
White fractions count exact RGB white, including edge pixels; the whole-screen
fraction includes system UI and is not a measure of emitted light.
"""

import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r41_20261121.windows import need, snapshot
from direct_camera_r41_20261121.light import extract_metadata, read_dng


LOGS = ('cal.log', 'day.log', 'even.log')
PHASE = r'[A-Za-z0-9][A-Za-z0-9_]*'
POS = r'[1-9][0-9]*'
STATE = (rf'({PHASE}) BL=({POS}) hwcId=0 ns=({POS}) '
         rf'rgb=(full|core|loaded|ring|inverse|dark) wake=({POS})')
PRE = re.compile('PRE ' + STATE)
POST = re.compile('POST ' + STATE + rf' count=({POS})')
FRAME = re.compile(rf'frame ({PHASE})__({POS}) ({POS})')
COLUMNS = ('phase profile scene sysfs_bl hwc_both refresh_both group_both sf_rgb_both '
           'exposure_ns iso frames wake_epoch band_white_frac_pre band_white_frac_post '
           'whole_white_frac_pre whole_white_frac_post native_readbacks').split()


def windows(log):
    state = None
    count = 0
    for number, raw in enumerate(log.read_text().splitlines(), 1):
        line = raw.strip()
        kind = line.split(maxsplit=1)[:1]
        if kind == ['PRE']:
            m = PRE.fullmatch(line)
            need(state is None and m, f'{log.name}:{number}: invalid or nested PRE')
            state, sizes = m.groups(), []
        elif kind == ['frame']:
            m = FRAME.fullmatch(line)
            need(state and m and m[1] == state[0] and int(m[2]) == len(sizes) + 1,
                 f'{log.name}:{number}: unbound or out-of-order frame')
            sizes.append(int(m[3]))
        elif kind == ['POST']:
            m = POST.fullmatch(line)
            need(state and sizes and m and m.groups()[:-1] == state and int(m[6]) == len(sizes),
                 f'{log.name}:{number}: mismatched POST or frame count')
            yield (*state, sizes)
            state = None
            count += 1
    need(state is None and count, f'{log.name}: empty log or unclosed window')


def source_masks(scene, width):
    x = np.arange(width) + 0.5  # physical pixel centers; CSS transitions are fractions of width
    ring = (x < .32 * width) | (x >= .68 * width)
    core = (x >= .42 * width) & (x < .58 * width)
    white = {'full': np.ones(width, bool), 'core': core, 'loaded': core | ring,
             'ring': ring, 'inverse': ~core, 'dark': np.zeros(width, bool)}[scene]
    edges = {'full': (), 'dark': (), 'core': (.42, .58), 'inverse': (.42, .58),
             'ring': (.32, .68), 'loaded': (.32, .42, .58, .68)}[scene]
    use = np.ones(width, bool)
    for edge in edges:
        use &= abs(x - edge * width) > 2
    return white, use


def screen(path, white, use):
    with Image.open(path) as im:
        need(im.format == 'PNG' and im.size == (1440, 3168), f'{path.stem}: expected original target PNG')
        if 'A' in im.getbands():
            need(im.getchannel('A').getextrema() == (255, 255), f'{path.stem}: nonopaque screenshot')
        rgb = np.asarray(im.convert('RGB'))
    h = len(rgb)
    band = slice(h // 5, 4 * h // 5)
    need(np.all(rgb[band, use, :] == (white[use] * 255)[None, :, None]),
         f'{path.stem}: wrong scene pixels in the central band')
    lit = (rgb == 255).all(axis=2)
    return lit, float(lit[band].mean()), float(lit.mean())


def verify_frame(path, size, ns, seen_raw):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size == size,
         f'{path.stem}: missing or wrong-size DNG')
    raw, tags = read_dng(path)
    m = extract_metadata(tags)
    need((m['make'], m['model'], m['iso'], m['width'], m['height'], m['orientation'],
          m['cfa_pattern_2x2'], m['focal_length_mm'], tags.get(33437), m['white_level'], raw.shape) ==
         ('Nothing', 'A001', 6400, 4080, 3072, 1, [1, 2, 0, 1], 5.56, [1.87], 1023, (3072, 4080)),
         f'{path.stem}: unexpected camera, ISO, geometry or lens')
    need(abs(1000 * m['exposure_us'] - ns) <= 1, f'{path.stem}: DNG exposure differs from window')
    # A renamed or metadata-only copy must not count as a second shutter release.
    digest = blake2b(raw, digest_size=16).digest()
    need(digest not in seen_raw, f'{path.stem}: duplicate RAW plane')
    seen_raw.add(digest)


def inventory(archive, phases, frames, partial_run):
    present = set()
    for f in (archive / 'frames').iterdir():
        if not f.name.lower().endswith(('.dng', '.partial')):
            continue
        if not partial_run or f.name.rsplit('__', 1)[0] in phases:
            present.add(f.name)
    need(present == frames, 'unbound, unfinished or missing DNG')
    for suffix in ('-pre.sf', '-post.sf', '-pre.png', '-post.png'):
        found = {p.name[:-len(suffix)] for p in archive.glob('*' + suffix)}
        need((found & phases if partial_run else found) == phases, f'unbound or missing {suffix} evidence')


def bind(archive, selected=None):
    logs = LOGS if selected is None else tuple(selected)
    need(logs and logs == tuple(k for k in LOGS if k in logs), 'select distinct logs in acquisition order')
    preflight = (archive / 'preflight.log').read_text()
    epochs = re.findall(r'^running\nactive: verified wake=([0-9]+)$', preflight, re.M)
    need(len(epochs) == 1, 'missing or ambiguous verified session at preflight')
    phases, files, seen_raw, rows = set(), set(), set(), []
    locked_sf = None
    for log in logs:
        for ph, bl, ns, scene, wake, sizes in windows(archive / log):
            need(ph not in phases and ph != 'pilot', f'{ph}: duplicate phase or non-window pilot')
            need(wake == epochs[0], f'{ph}: wake differs from verified session')
            expected_bl = '512' if log == 'even.log' else '6692'
            need(bl == expected_bl, f'{ph}: expected fixed BL {expected_bl} for this series')
            labels = [word.removesuffix('Ret') for word in ph.split('_')
                      if word.removesuffix('Ret') in ('full', 'core', 'loaded', 'ring', 'inverse', 'dark')]
            need(not labels or labels == [scene], f'{ph}: phase label contradicts the actual scene')
            pre = snapshot(archive / f'{ph}-pre.sf')
            need(pre == snapshot(archive / f'{ph}-post.sf'), f'{ph}: SF mode or matrix changed')
            if locked_sf is None:
                locked_sf = pre
            need(pre == locked_sf, f'{ph}: SF mode or matrix differs between windows')
            white, use = source_masks(scene, 1440)
            a, band_pre, whole_pre = screen(archive / f'{ph}-pre.png', white, use)
            b, band_post, whole_post = screen(archive / f'{ph}-post.png', white, use)
            # Allow edge rasterization and small system UI changes (e.g. the clock).
            # Pixel comparison catches compensating changes hidden by equal fractions.
            need(np.count_nonzero((a != b)[:, use]) <= .001 * a.size,
                 f'{ph}: whole-screen white mask changed outside stripe edges')
            for i, size in enumerate(sizes, 1):
                name = f'{ph}__{i}.dng'
                verify_frame(archive / 'frames' / name, size, int(ns), seen_raw)
                files.add(name)
            phases.add(ph)
            fractions = (band_pre, band_post, whole_pre, whole_post)
            rows.append((ph, 'active_0x8e', scene, bl, *pre[0], ns, 6400, len(sizes), wake,
                         *(f'{x:.8f}' for x in fractions), 'none'))
    inventory(archive, phases, files, logs != LOGS)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--logs', nargs='+', choices=LOGS)
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.logs)
    except OSError as exc:
        ap.error(exc.strerror or 'unreadable archive input')
    except ValueError as exc:
        ap.error(str(exc))
    out = csv.writer(sys.stdout, lineterminator='\n')
    out.writerow(COLUMNS)
    out.writerows(rows)


if __name__ == '__main__':
    main()
