#!/usr/bin/env python3
"""R41: simultaneous rolling-shutter profiles of interleaved RGB stimulus fields.

python -B tiles.py TILE_FRAMES [--plot frame.png] > tiles.csv
Each layout (rgb, bgr) needs cal__1..3, short__1..4, medium__1..3 prefixed
with the layout and '_', extension .dng. A001 1x, ISO 6400, 1250/200/500 us.
All measurements use signed native GBRG sites in the R33 ROI. Only the mask
classifier uses a 3x3 spatial mean and combines the greens. The three CALs
must agree at >1.6 dominance, >20 DN, without clipped/floored neighborhoods;
then erode two cells. Require >=8 centers of EACH color on EVERY cell row.
The two CAL layouts must show opposite cyclic orders along the camera x axis.

For registration, classify the test image afresh, BEFORE applying the CAL
mask. Select well-lit rows by the unmasked median winning-channel brightness
(>20 DN and >=70% of its row P90). In each vertical quarter require >=10 lit
rows and >=80% of each color's frozen centers to have the correct strong
winner there. Weak/conflicting predictions count as misses. Test samples
are never moved or discarded on the basis of their observed color or depth.

Select the deepest G1/local-plateau minimum as in R33; require a bounded
half-depth dip at least 3 cell samples wide and a drop >5 robust shoulder
scales (1.4826*MAD on smoothed samples 16..40 cells away on either side).
This rejects noise-only anchors; it is not a detection-limit estimate.
R36 measures every other site
at that same physical RAW y (odd R/G2 rows are interpolated), against its
own plateau. No alignment claimed without both bounded half-depth centers.
Site mean and local plateau must both exceed 20 DN and no selected stored
sample may clip or hit zero. G2 on green is supplementary. Units: camera
DN and RAW rows, not emitter spectra, luminance, time or physical PWM Hz.
"""

import argparse
import csv
from hashlib import blake2b
from pathlib import Path
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as windows

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r36_20261120.channels import characterize
from direct_camera_r41_20261121.measure import ROI, SITES, decode_dng_bytes, extract_metadata


LAYOUTS = ('rgb', 'bgr')
GROUPS = {'cal': (3, 1250), 'short': (4, 200), 'medium': (3, 500)}
COLORS = ('red', 'green', 'blue')
# SITES is ordered R,G1,B,G2; these indices select their CAL stimulus masks.
COLOR_INDEX = (0, 1, 2, 1)
MIN_COUNT = 8
HALO = 3  # 1 for smoothing + 2 for erosion; retain full R33 ROI at edges


def read_frame(path, exposure, seen):
    raw, tags = decode_dng_bytes(path.read_bytes())
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['orientation'], m['width'], m['height'],
         m['focal_length_mm'], m['iso'], m['cfa_pattern_2x2']) !=
            ('Nothing', 'A001', 1, 4080, 3072, 5.56, 6400, [1, 2, 0, 1])
            or not abs(m['exposure_us'] - exposure) <= 0.001):
        raise ValueError('unexpected camera, CFA, ISO or exposure')
    y0, y1, x0, x1 = ROI
    patch = raw[2*(y0-HALO):2*(y1+HALO), 2*(x0-HALO):2*(x1+HALO)]
    # A renamed copy cannot serve as an independent exposure.
    ident = blake2b(patch.tobytes(), digest_size=16).digest()
    if ident in seen:
        raise ValueError(f'duplicate raw patch from {seen[ident]}')
    seen[ident] = path.stem
    stored = np.stack([patch[i//2::2, i%2::2] for _, i in SITES])
    black = np.array([m['black_levels'][i] for _, i in SITES])
    return stored - black[:, None, None], stored >= m['white_level'], stored == 0, m['exposure_us']


def classify(frame):
    signal, clip, floor, _ = frame
    rgb = np.stack((signal[0], (signal[1]+signal[3])/2, signal[2]))
    rgb = windows(rgb, (3, 3), axis=(1, 2)).mean(axis=(-1, -2))
    runner, top = np.sort(rgb, axis=0)[1:]
    bad = windows((clip | floor).any(axis=0), (3, 3)).any(axis=(-1, -2))
    winner = np.where((top > 20) & (top > 1.6*runner) & ~bad, rgb.argmax(axis=0), -1)
    return winner, top


def calibration(frames):
    winners = np.stack([classify(f)[0] for f in frames])
    masks = np.stack([windows((winners == c).all(axis=0), (5, 5)).all(axis=(-1, -2))
                      for c in range(3)])
    labels = np.where(masks.any(axis=0), masks.argmax(axis=0), -1)
    # Camera orientation need not match CSS. Compare order, not absolute stripe position.
    forward = total = 0
    for row in labels:
        steps = np.diff(row[row >= 0]) % 3
        forward += int((steps == 1).sum())
        total += np.count_nonzero(steps)
    return masks, forward/total if total else None


def registration(frame, masks):
    winner, top = classify(frame)
    winner, top = winner[2:-2, 2:-2], top[2:-2, 2:-2]
    brightness = np.median(top, axis=1)
    lit = (brightness > 20) & (brightness >= 0.70*np.percentile(brightness, 90))
    result = []
    for c, mask in enumerate(masks):
        cells = mask & lit[:, None]
        good = cells & (winner == c)
        quarters = np.array_split(np.arange(len(lit)), 4)
        fractions = [good[q].sum()/cells[q].sum() for q in quarters if cells[q].any()]
        worst = min(fractions) if len(fractions) == 4 else None
        min_rows = min(lit[q].sum() for q in quarters)
        result.append(dict(reg_lit_rows=lit.sum(), reg_min_lit_rows_quarter=min_rows,
                           reg_cells_n=cells.sum(), reg_match_frac=good.sum()/cells.sum() if cells.any() else None,
                           reg_min_quarter_frac=worst, reg_ok=int(min_rows >= 10 and worst is not None and worst >= .80)))
    return result


def anchor(green):
    """R33 valid 3/81-cell profile; select only on G1, never retry an easier event."""
    local = np.median(windows(green, 81), axis=1)
    if np.any(local <= 0):
        return None
    relative = green[40:-40]/local
    i = int(relative.argmin())
    shoulders = np.r_[green[i:i+25], green[i+56:i+81]]
    scatter = 1.4826*np.median(abs(shoulders-np.median(shoulders)))
    if local[i]-green[i+40] <= 5*scatter:
        return None
    half = (1+relative[i])/2
    left = np.flatnonzero(relative[:i] >= half)
    right = np.flatnonzero(relative[i+1:] >= half)
    if not left.size or not right.size or i + right[0] - left[-1] < 3:
        return None
    return 2*(ROI[0]+41+i)


def measure(phase, n, frame, masks, order, reversed_ok):
    reg = registration(frame, masks)
    s, cl, fl = (a[:, HALO:-HALO, HALO:-HALO] for a in frame[:3])
    counts = masks.sum(axis=2)
    mask_ok = counts.min() >= MIN_COUNT
    common = ('insufficient_mask' if not mask_ok else 'layout_order_unverified' if not reversed_ok
              else 'registration_failed' if not all(d['reg_ok'] for d in reg) else 'ok')
    results, profiles, coordinates = [], [], []
    for j, ((site, bayer), c) in enumerate(zip(SITES, COLOR_INDEX)):
        mask, count = masks[c], counts[c]
        samples = s[j][mask]
        mean = samples.mean() if samples.size else None
        clip, floor = cl[j][mask].sum(), fl[j][mask].sum()
        gate = ('no_samples' if mean is None else 'clipped' if clip else 'storage_floor' if floor
                else 'below_signal_gate' if mean <= 20 else 'ok')
        rows = 2*np.arange(ROI[0]+1, ROI[1]-1) + bayer//2
        profile = None
        if mask_ok and gate == 'ok':
            signal = (s[j]*mask).sum(axis=1)/count
            profile = np.convolve(signal, np.ones(3)/3, 'valid')
        profiles.append(profile)
        coordinates.append(rows)
        results.append(dict(phase=phase, frame_n=n, exposure_us=frame[3], stimulus=COLORS[c], site=site,
                            cal_coverage_frac=mask.mean(), cal_min_cells_row=count.min(),
                            cal_rows_below_min=(count < MIN_COUNT).sum(), cal_forward_frac=order,
                            cal_reverse_pair_ok=int(reversed_ok), **reg[c], mean_dn=mean, clip_n=clip,
                            floor_n=floor, site_gate=gate, status=common if common != 'ok' else gate,
                            fixed_g1_raw_y=None, local_plateau_dn=None, dn_at_g1=None, depth_at_g1_pct=None,
                            half_center_raw_y=None, half_center_minus_g1_rows=None))

    event = anchor(profiles[1]) if results[1]['status'] == 'ok' else None
    # Qualify G1's bounded crossing before allowing ANY fixed-row depth.
    for j in (1, 0, 2, 3):
        r = results[j]
        if r['status'] != 'ok':
            continue
        if event is None:
            r['status'] = 'no_qualified_g1_event'
            continue
        try:
            plateau, at, depth, _, center = characterize(coordinates[j], profiles[j], event)
            if plateau <= 20:
                r['status'] = 'low_local_plateau'
            elif j == 1 and center is None:
                r['status'] = 'unbounded_g1_event'
        except ValueError:
            r['status'] = 'no_local_plateau'
        if r['status'] != 'ok':
            if j == 1:
                event = None
            continue
        r.update(local_plateau_dn=plateau, dn_at_g1=at, depth_at_g1_pct=depth, half_center_raw_y=center)
        if center is not None:
            r['half_center_minus_g1_rows'] = center-results[1]['half_center_raw_y']

    joint = all(r['status'] == 'ok' for r in results[:3])
    aligned = joint and all(r['half_center_raw_y'] is not None for r in results[:3])
    for r in results:
        r.update(fixed_g1_raw_y=event, rgb_depth_usable=int(joint), rgb_centers_usable=int(aligned))
    return results, coordinates, profiles


def plot_frame(path, frame, results, coordinates, profiles):
    # Publish only the derived profiles. Neither screenshots nor RAW crops are needed.
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (780, 440), 'white'); draw = ImageDraw.Draw(im)
    event = results[1]['fixed_g1_raw_y']
    xy = lambda row, level: (65 + (row-event+80)*4.25, 360 - level*240)
    draw.text((55, 12), f"{results[0]['phase']} #{results[0]['frame_n']} | {frame[3]:g} us | signal / local plateau", fill='black')
    for level in (0, .25, .5, .75, 1, 1.25):
        _, y = xy(event, level); draw.line((65,y,745,y), fill='#dddddd'); draw.text((26,y-6),f'{level:g}',fill='black')
    for row in range(event-80, event+81, 20):
        x, _ = xy(row, 0); draw.line((x,60,x,360), fill='#888888' if row==event else '#eeeeee'); draw.text((x-14,367),str(row),fill='black')
    draw.text((325,390), 'Physical RAW row', fill='black')
    for j, color in enumerate(('#b43838','#117442','#2754ae')):
        points = [xy(y, level) for y, level in zip(coordinates[j], profiles[j]/results[j]['local_plateau_dn']) if abs(y-event)<=80]
        draw.line(points, fill=color, width=3); draw.text((230+j*130, 416),f"{COLORS[j]} / {results[j]['site']}",fill=color)
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', type=Path, metavar='TILE_FRAMES')
    ap.add_argument('--plot', type=Path, metavar='PNG', help='first frame with qualified RGB depths in fixed inventory order')
    args = ap.parse_args()
    expected = {f'{layout}_{group}__{n}.dng' for layout in LAYOUTS for group, (size, _) in GROUPS.items()
                for n in range(1, size+1)}
    seen, cals, output = {}, {}, []
    representative = None
    try:
        found = {p.name for p in args.frames.iterdir() if p.suffix.lower() == '.dng'}
        if expected != found:
            raise ValueError(f'tile inventory: {len(expected-found)} missing, {len(found-expected)} unexpected DNGs')

        def load(layout, group, n):
            path = args.frames / f'{layout}_{group}__{n}.dng'
            try:
                return read_frame(path, GROUPS[group][1], seen)
            except ValueError as exc:
                raise ValueError(f'{path.stem}: {exc}') from None

        for layout in LAYOUTS:
            cals[layout] = calibration(load(layout, 'cal', n) for n in range(1, 4))
        a, b = (cals[key][1] for key in LAYOUTS)
        reversed_ok = (a is not None and b is not None and
                       ((a >= .8 and b <= .2) or (b >= .8 and a <= .2)))
        for layout in LAYOUTS:
            for group in ('short', 'medium'):
                for n in range(1, GROUPS[group][0]+1):
                    frame = load(layout, group, n)
                    rows, coords, profiles = measure(f'{layout}_{group}', n, frame, *cals[layout], reversed_ok)
                    output.extend(rows)
                    if args.plot and representative is None and rows[0]['rgb_depth_usable']:
                        representative = frame, rows, coords, profiles
        if args.plot:
            if args.plot.suffix.lower() != '.png' or args.plot.exists():
                raise ValueError('--plot requires a new .png path')
            if representative:
                plot_frame(args.plot, *representative)
            else:
                print('No qualified RGB frame for plot.', file=sys.stderr)
    except (ValueError, OSError) as exc:
        ap.error(exc.strerror if isinstance(exc, OSError) else str(exc))

    writer = csv.DictWriter(sys.stdout, fieldnames=output[0], lineterminator='\n')
    writer.writeheader()
    for row in output:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
