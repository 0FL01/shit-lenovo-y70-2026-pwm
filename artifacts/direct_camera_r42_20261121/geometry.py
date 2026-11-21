#!/usr/bin/env python3
"""Qualify the frozen R42 ROI from independent 1.25 ms CALs.

python3 -B geometry.py FRAMES [--rows | --registration]
Coordinates are half-open native Bayer cells; DN = stored G1 minus tagged black.
Check every row including 20 above/below the ROI. Use a horizontal 9-cell
median, never a vertical filter, average of releases, or test-frame minimum.
Core/loaded must have a connected bright stripe between two dark witnesses;
inverse must have the opposite stripe at the same place. Report the run at
80% of the local *same-row* contrast (towards the interior, dark for inverse).
Margins count spare filtered centers, not an optical resolution below 9 cells.
Full must illuminate the guarded rectangle; ring/dark must extinguish its
center. These optical swaps distinguish a stimulus from chrome or a cable.
--registration verifies each available day/evening stripe DNG against the
CAL edges. Four fixed horizontal profiles average ALL rows in each vertical
quarter. This is a registration check at quarter resolution, not a dip search
or a certificate of complete acquisition. Only finalized .dng files are read.
"""

import argparse
from collections import Counter
from contextvars import ContextVar
import csv
from hashlib import blake2b
from pathlib import Path
import re
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r41_20261121.measure import decode_dng_bytes, extract_metadata


# The EXIF tag is an acquisition constraint, not a rotation of the native CFA.
EXPECTED_ORIENTATION = ContextVar('EXPECTED_ORIENTATION', default=1)
Y0, Y1, X0, X1 = 630, 1250, 754, 799
GUARD, RADIUS = 20, 4
YS = np.arange(Y0-GUARD, Y1+GUARD)
INNER = slice(GUARD, -GUARD)
SCENES = ('full', 'core', 'loaded', 'ring', 'dark', 'inverse')
GAPS = ((680, 700), (851, 871))
SHOULDERS = ((740, 750), (806, 816))  # both outside analysis ROI, inside core
WINGS = ((620, 645), (930, 1090))  # presence witnesses only, not measurement pixels


def require(condition, msg):
    if not condition:
        raise ValueError(msg)


def check_min(values, threshold, label):
    a = np.asarray(values).reshape(len(YS), -1)
    i, j = np.unravel_index(np.argmin(a), a.shape)
    require(a[i, j] >= threshold, f'{label}: {a[i,j]:.3f} < {threshold:g} at cell y={YS[i]}')


def check_max(values, threshold, label):
    check_min(-values, -threshold, 'negative of ' + label)


def read_native(path, exposure_us):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    require((m['make'], m['model'], m['focal_length_mm'], m['iso'], m['orientation'],
             m['width'], m['height'], m['cfa_pattern_2x2'], m['white_level'], raw.shape) ==
            ('Nothing', 'A001', 5.56, 6400, EXPECTED_ORIENTATION.get(), 4080, 3072, [1, 2, 0, 1], 1023, (3072, 4080))
            and abs(m['exposure_us']-exposure_us) <= .001, 'wrong native geometry, scale or capture settings')
    b, white = m['black_levels'][0], m['white_level']
    require(np.isfinite(b) and 0 < b < white, 'invalid G1 BlackLevel')
    return raw, b, white


def strips(path, seen):
    raw, b, white = read_native(path, 1250)
    raw = raw[2*YS[0]:2*(YS[-1]+1)]
    patch = raw[:, 2*(X0-GUARD):2*(X1+GUARD)]
    require(not ((patch == 0) | (patch >= white)).any(), 'stored floor/clip in guarded ROI (any CFA)')
    digest = blake2b(patch.tobytes(), digest_size=16).digest()
    require(digest not in seen, 'duplicate native CAL patch')
    seen.add(digest)

    g = raw[::2, ::2]  # GBRG, G1 only; no debayer or EXIF rotation
    base = WINGS[0][0]
    src = g[:, base-RADIUS:GAPS[1][1]+RADIUS]
    require(not ((src == 0) | (src >= white)).any(), 'stored G1 floor/clip in geometry evidence')
    v = np.median(sliding_window_view(src, 2*RADIUS+1, axis=1), axis=2) - b

    def band(l, r):
        return v[:, l-base:r-base]

    # The right remote wing can contain a cable and occasional saturated sites.
    # Use its row median only as a witness; exclude rails, require >=90% support.
    a, z = WINGS[1]
    far = g[:, a:z].astype(float)
    ok = (far > 0) & (far < white)
    check_min(ok.mean(axis=1), .90, 'right wing usable fraction')
    far[~ok] = np.nan
    wings = np.column_stack((np.median(band(*WINGS[0]), axis=1), np.nanmedian(far, axis=1)-b))
    return band, wings


def measure(path, scene, seen, full_shapes):
    band, wings = strips(path, seen)
    roi, guard = band(X0, X1), band(X0-GUARD, X1+GUARD)
    gaps = np.column_stack([band(*p) for p in GAPS])

    def reference(pair):
        return sum(np.median(band(*p), axis=1) for p in pair)[:, None]/2

    gap, shoulder = reference(GAPS), reference(SHOULDERS)
    # The original Android layouts have both wings lit except on core and dark.
    # A static UI bar cannot pass the positive AND negative spatial controls.
    if scene in ('core', 'dark'):
        check_max(wings, 20, 'black wing median DN')
    else:
        check_min(wings, 20, 'lit wing median DN')
    if scene in ('full', 'inverse'):
        check_min(gaps, 20, 'lit flank DN')
    else:
        check_max(gaps, 20, 'black gap DN')

    shape = bounds = level = vs_full = None
    if scene in ('full', 'core', 'loaded'):
        check_min(roi, 20, 'lit interior DN')
    else:
        check_max(roi, 20, 'black interior DN')

    if scene == 'full':
        check_min(shoulder, 20, 'full shoulders DN')
        check_min(guard, 20, 'full guard DN')
        level = guard/gap  # flank witnesses independent of the central rectangle
        check_min(level, .80, 'full guard / full flank plateau')
        shape = roi/shoulder
    elif scene in ('core', 'loaded', 'inverse'):
        sign = -1 if scene == 'inverse' else 1
        check_min(sign*(shoulder-gap), 20, 'same-row local contrast DN')
        x = np.arange(GAPS[0][0], GAPS[1][1])
        q = (band(x[0], x[-1]+1)-gap)/(shoulder-gap)
        level = q[:, X0-x[0]:X1-x[0]]
        check_min(level, .80, 'interior fraction towards stripe plateau')
        # Nearest outside sample on each side bounds the connected plateau.
        # Both ends of the search MUST be outside; no default-to-image-edge pass.
        good = q >= .80
        require(not (good[:, 0] | good[:, -1]).any(), 'unbounded stripe')
        left = np.where(~good & (x < X0), x, x[0]-1).max(axis=1)+1
        right = np.where(~good & (x >= X1), x, x[-1]+1).min(axis=1)
        check_min(X0-left, GUARD, 'left edge margin (cells)')
        check_min(right-X1, GUARD, 'right edge margin (cells)')
        bounds = (left, right)
        if sign > 0:
            # Both independent full exposures, normalized to their own two
            # same-row shoulders. Do not divide unsynchronized RAW row levels.
            vs_full = np.minimum.reduce([level/f for f in full_shapes])
            check_min(vs_full, .70, 'interior fraction / normalized full')
    inner = roi[INNER]
    return dict(shape=shape, bounds=bounds, dn=(inner.min(), inner.max()),
                level=level[INNER].min() if level is not None else None,
                vs_full=vs_full[INNER].min() if vs_full is not None else None)


def run(frames):
    expected = {f'cal_{s}__{i}.dng' for s in SCENES for i in (1, 2)}
    found = {p.name for p in frames.glob('cal_*') if p.suffix.lower() in ('.dng', '.partial')}
    require(found == expected, 'expected exactly two CAL DNGs per scene and no partials')
    results, seen, full_shapes = {}, set(), []
    for scene in SCENES:
        for i in (1, 2):
            tag = f'cal_{scene}__{i}'
            try:
                result = measure(frames/(tag+'.dng'), scene, seen, full_shapes)
            except ValueError as exc:
                raise ValueError(f'{tag}: {exc}') from None
            results[tag] = result
            if scene == 'full':
                full_shapes.append(result['shape'])
    # Independent edge registers, including the inverse polarity; same y only.
    bounds = np.array([r['bounds'] for r in results.values() if r['bounds'] is not None])
    spread = np.ptp(bounds, axis=0)
    check_max(spread.T, 2*RADIUS, 'cross-CAL edge spread (cells)')
    return results, spread


STRIPE = r'(?:core|loaded)(?:Ret)?'
TEST = re.compile(rf'(?:(d200|d312|d500)_{STRIPE}|e_{STRIPE}_(flat|short))__[1-9]\d*\.dng')
EXPOSURE_US = dict(d200=200, d312=312.5, d500=500, flat=25000, short=4000)


def register(path, us, ref, seen):
    raw, black, white = read_native(path, us)
    lo, hi = GAPS[0][0], GAPS[1][1]
    g = raw[2*Y0:2*Y1:2, 2*(lo-RADIUS):2*(hi+RADIUS):2]
    require(not ((g == 0) | (g >= white)).any(), 'stored G1 floor/clip in registration strip')
    digest = blake2b(g.tobytes(), digest_size=16).digest()
    require(digest not in seen, 'duplicate test strip')
    seen.add(digest)
    # The exposure controls temporal averaging. Here every quarter always uses
    # all 155 rows and the identical two gap and two shoulder coordinates.
    profiles = g.reshape(4, (Y1-Y0)//4, -1).mean(axis=1) - black
    smoothed = np.median(sliding_window_view(profiles, 2*RADIUS+1, axis=1), axis=2)
    metrics = []
    for k, p in enumerate(smoothed):
        def gate(ok, reason):
            require(ok, f'Q{k+1}: {reason}')

        gaps = [p[l-lo:r-lo] for l, r in GAPS]
        shoulder = [np.median(p[l-lo:r-lo]) for l, r in SHOULDERS]
        # Estimate dispersion on unsmoothed quarter means (remove each gap's
        # own median). Geometry S/N is not the event analysis's per-site gate.
        witness = [profiles[k, l-lo+RADIUS:r-lo+RADIUS] for l, r in GAPS]
        noise = 1.4826*np.median(np.abs(np.concatenate([a-np.median(a) for a in witness])))
        gap = np.mean([np.median(a) for a in gaps])
        contrast = np.mean(shoulder)-gap
        gate(contrast >= max(5., 8*noise), f'insufficient stripe/gap contrast {contrast:.2f} DN (noise {noise:.2f})')
        gate(max(a.max() for a in gaps) <= .25*min(shoulder), 'one or both flank gaps not dark')
        q = (p-gap)/contrast
        ratio = float(q[X0-lo:X1-lo].min())
        gate(ratio >= .80, f'interior/plateau {ratio:.3f} < 0.80')
        bad = np.flatnonzero(q < .80) + lo
        left, right = bad[bad < X0], bad[bad >= X1]
        gate(left.size and right.size, 'unbounded stripe')
        edges = np.array([left[-1]+1, right[0]])
        lm, rm = X0-edges[0], edges[1]-X1
        gate(min(lm, rm) >= GUARD, f'edge margins {lm}:{rm} < required {GUARD}')
        delta = np.max(np.abs(edges-ref[k]))
        gate(delta <= 2*RADIUS, f'edge shift {delta:g} cells from independent CAL')
        metrics.append((lm, rm, ratio, delta, contrast))
    a = np.array(metrics)
    return int(a[:, 0].min()), int(a[:, 1].min()), a[:, 2].min(), a[:, 3].max(), a[:, 4].min()


def registration(frames, results):
    # Frozen per-quarter representative of both complementary polarities and
    # both CAL releases. Never update it from a test result or fit translations.
    edges = np.array([r['bounds'] for r in results.values() if r['bounds'] is not None])
    ref = np.median(edges[:, :, INNER].reshape(6, 2, 4, -1), axis=(0, 3)).T
    paths = sorted((p, m[1] or m[2]) for p in frames.glob('*.dng') if (m := TEST.fullmatch(p.name)))
    require(paths, 'no finalized day/evening stripe test DNGs in this snapshot')
    out = csv.writer(sys.stdout, lineterminator='\n')
    out.writerow(('frame', 'status', 'min_left', 'min_right', 'min_roi_to_plateau',
                  'max_cal_shift', 'min_contrast_dn', 'reason'))
    seen, ok, phases = set(), [], Counter()
    for path, group in paths:
        phases[path.stem.split('__')[0]] += 1
        try:
            a = register(path, EXPOSURE_US[group], ref, seen)
        except (ValueError, OSError) as exc:
            out.writerow((path.stem, 'FAIL', '', '', '', '', '', exc.strerror if isinstance(exc, OSError) else str(exc)))
        else:
            ok.append(a)
            out.writerow((path.stem, 'PASS', *a[:2], f'{a[2]:.3f}', f'{a[3]:g}', f'{a[4]:.2f}', ''))
    print('Registration snapshot (final inventory not checked):',
          ', '.join(f'{p}={n}' for p, n in sorted(phases.items())), file=sys.stderr)
    summary = f'{len(ok)}/{len(paths)} PASS'
    if ok:
        mins = np.min(ok, axis=0)
        summary += (f'; passing min L:R={mins[0]:g}:{mins[1]:g} cells, min ROI/plateau={mins[2]:.3f}, '
                    f'max CAL shift={max(a[3] for a in ok):g} cells')
    print(summary, file=sys.stderr)
    return int(len(ok) != len(paths))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='FRAMES')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--rows', action='store_true', help='emit per-row CAL edge CSV including vertical guards')
    mode.add_argument('--registration', action='store_true', help='per-test registration CSV; CAL runs once')
    args = ap.parse_args()
    try:
        results, spread = run(args.frames)
        if args.registration:
            return registration(args.frames, results)
    except (ValueError, OSError) as exc:
        ap.exit(1, 'FAIL: ' + (exc.strerror if isinstance(exc, OSError) else str(exc)) + '\n')
    if args.rows:
        out = csv.writer(sys.stdout, lineterminator='\n')
        out.writerow(('cal', 'bayer_y', 'left_inclusive', 'right_exclusive', 'left_margin', 'right_margin'))
        for tag, result in results.items():
            if result['bounds'] is not None:
                for y, l, r in zip(YS, *result['bounds']):
                    out.writerow((tag, y, l, r, X0-l, r-X1))
        return
    print('CAL                ROI_G1_DN_min:max  min_level  min_vs_full  min_margin_L:R')
    fmt = lambda x: '-' if x is None else f'{x:.3f}'
    for tag, r in results.items():
        margin = '-'
        if r['bounds'] is not None:
            l, h = r['bounds']
            margin = f'{X0-l[INNER].max()}:{h[INNER].min()-X1}'
        print(f'{tag:17} {r["dn"][0]:7.2f}:{r["dn"][1]:6.2f} {fmt(r["level"]):>10} '
              f'{fmt(r["vs_full"]):>12} {margin:>15}')
    print(f'PASS: 12 CALs, ROI y=[{Y0},{Y1}) x=[{X0},{X1}); all {len(YS)} rows incl. guards; '
          f'max edge spread L:R={spread[0].max()}:{spread[1].max()} cells; guarded CFA clip/floor=0/0')


if __name__ == '__main__':
    sys.exit(main())
