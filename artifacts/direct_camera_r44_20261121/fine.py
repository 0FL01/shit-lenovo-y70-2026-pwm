#!/usr/bin/env python3
"""python3 -B fine.py FRAMES > fine.csv — spatial ripple, not broad-trough D or Hz.

R42 fixed ROI, signed native G1. R35 spacing.py convention: remove quadratic
shading, fit a separate quadratic per light segment plus three common spatial
harmonics. Report the *fundamental semi-amplitude* in percent of that baseline
(twice this is the fitted fundamental's peak-to-trough, not the total waveform).
Search only R35's 105..315 RAW-row band. A first fit proposes a pitch; R35's
like-phase deficit mask avoids removing regularly repeated fine minima as if
each were a broad event. Final fits exclude the deficits and 40 cells per side.

Require >=3 disjoint complete pitch-length intervals (>=2 adjacent), coherent
fundamentals in >=3 and >=75% of intervals. The empirical semi-amplitude gate
is the largest of one DN, 3x the same-image interleaved-column noise amplitude,
and 3x the between-interval standard error of the two Fourier coefficients.
This is a repeatability/sensitivity screen, not a confidence limit; a blank
pitch is unidentifiable, not a zero. It does not exclude other pitches.

free_* checks for a resolved wave in each frame. locked_* tests one common
pitch on every frame, even when the fitted amplitude falls below the gate.
Prefer a reproducible initial OFF window (low/500 us first). Never train on
ON or return. Without a resolved OFF reference, test the prespecified R35
177.35-RAW-row template, explicitly labelled historical. This tests sensitivity
at that scale; it does not establish a local OFF ripple or its suppression.
Only free_pitch_raw for resolved free fits and lock_pitch_raw (the tested
scale) are published. Counts are pitch-length
intervals on retained light rows, never periods inferred from display mode.
Join phase/frame to closed windows and check drive, HDR, refresh and geometry
before attributing a difference to DC. Missing windows do not prove why.
"""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r35_20261120.spacing import intervals
from direct_camera_r42_20261121.measure import ROI, inputs, read_sites, sample


EXPOSURES = {'125': 125., '200': 200., '312': 312.5, '500': 500.}
PHASES = {f'day_{state}{drive}_{t}': us for drive in ('', 'Low')
          for state in ('off', 'on', 'ret') for t, us in EXPOSURES.items()
           if (drive == 'Low' and t != '125') or (drive == '' and t != '500')}
BAND = (105, 315)  # RAW rows, independent of the frame's acquisition label
# R35/spacing.csv, h120 initial BL 3600, 500 us, median of 3 spatial fits.
ARCHIVE_PITCH = 177.35


def load(path, us):
    meta, sites = read_sites(path, None)  # camera, geometry, CFA and ISO gates
    g, stats = sample(sites['G1'], meta['black_levels'][0], meta['white_level'], False)
    row = dict(exposure_us=meta['exposure_us'], **stats)
    if abs(meta['exposure_us']-us) > .001:
        return dict(row, gate='exposure_mismatch'), None
    if stats['gate'] != 'ok':
        return row, None
    p = g.mean(axis=1)
    y = np.linspace(-1, 1, len(p))
    shade = np.polyval(np.polyfit(y, p, 2), y)
    if not np.all(np.isfinite(shade) & (shade > 0)):
        return dict(row, gate='invalid_shading'), None
    # Difference estimates full-width row noise at the *illuminated* level.
    # Scale accounts for the unequal 23/22 column counts in this G1 ROI.
    a, b = g[:, ::2], g[:, 1::2]
    diff = (a.mean(1)-b.mean(1)) * np.sqrt(a.shape[1]*b.shape[1])/g.shape[1]
    return row, (np.column_stack((p/shade, diff/shade)), shade)


def light_runs(deep):
    masked = np.convolve(deep.astype(int), np.ones(81, int), 'same') > 0
    return [(a, b) for a, b in intervals(~masked) if b-a >= 50]


def smooth(p, n):
    return np.convolve(np.pad(p, n//2, mode='edge'), np.ones(n)/n, 'valid')


def runs_at(p, pitch):
    # R35 carrier.notch_mask, expressed in this ROI's native Bayer cells.
    v = smooth(p, 5)
    y = np.arange(len(p)); lag = pitch/2
    at = lambda n: np.interp(y+n*lag, y, v)
    expected = np.where(y < lag, 2*at(1)-at(2), np.where(
        y > y[-1]-lag, 2*at(-1)-at(-2), (at(-1)+at(1))/2))
    return light_runs(expected-v > .20*p.mean())


def harmonics(x, pitch):
    angle = 2*np.pi*x[:, None]*np.arange(1, 4)/pitch
    return np.column_stack((np.sin(angle), np.cos(angle)))


class LightFit:
    """R35 spacing.fit: same light-row coordinates, trend projection and units."""

    def __init__(self, values, runs):
        self.runs = runs
        self.idx = np.concatenate([np.arange(a, b) for a, b in runs])
        self.x = 2*self.idx  # fixed origin within this ROI; pitch in RAW rows
        trend = np.zeros((len(self.x), 3*len(runs)))
        start = 0
        for j, (a, b) in enumerate(runs):
            u = np.linspace(-1, 1, b-a)
            trend[start:start+b-a, 3*j:3*j+3] = np.column_stack((u**0, u, u*u))
            start += b-a
        self.q = np.linalg.qr(trend, mode='reduced')[0]
        self.v = values[self.idx]
        self.z = self.v-self.project(self.v)

    def project(self, v):
        return self.q @ (self.q.T @ v)

    def fit(self, pitch):
        h = harmonics(self.x, pitch)
        x = h-self.project(h)
        c = np.linalg.lstsq(x, self.z, rcond=None)[0]
        return self.z-x@c, c, h

    def best(self):
        def cost(p):
            residual = self.fit(p)[0][:, 0]
            return residual @ residual
        lo, hi = BAND
        seed = min(range(lo, hi+1, 2), key=cost)
        return min(np.arange(max(lo, seed-2), min(hi, seed+2)+.01, .05), key=cost)


def assess(data, pitch):
    v, shade = data
    runs = runs_at(v[:, 0], pitch)
    out = dict(status='insufficient_light_intervals', kept_cells=sum(b-a for a, b in runs),
               light_runs=';'.join(f'{a}:{b}' for a, b in runs), complete_n=0, longest_n=0)
    if not runs:
        return out
    f = LightFit(v, runs)
    _, c, h = f.fit(pitch)
    detrended = f.v-f.project(f.v-h@c)  # remove only nuisance trend, not the wave
    coefs = []
    start = 0
    for a, b in runs:
        edges = np.ceil(np.arange(1+int(2*(b-a)/pitch))*pitch/2).astype(int)
        consecutive = 0
        for lo, hi in zip(edges, edges[1:]):
            # Count only whole illuminated intervals, never span a masked gap.
            if np.mean(v[a+lo:a+hi, 0]*shade[a+lo:a+hi]) < 20:
                consecutive = 0
                continue
            sl = slice(start+lo, start+hi)
            x = np.column_stack((h[sl], np.ones(hi-lo)))
            coefs.append(np.linalg.lstsq(x, detrended[sl], rcond=None)[0][[0, 3]])
            consecutive += 1
            out['longest_n'] = max(out['longest_n'], consecutive)
        start += b-a
    n = len(coefs); out['complete_n'] = n
    if n < 3 or out['longest_n'] < 2:
        return out
    # Fundamental vectors (sin,cos), percent of local light, not broad depth D.
    signal, noise = (100*np.array(coefs)).transpose(2, 0, 1)
    vec = 100*c[[0, 3], 0]; amp = np.linalg.norm(vec)
    noise_rms = np.sqrt(np.square(noise).sum(axis=1).mean())
    repeat_sem = np.sqrt(np.square(signal-signal.mean(axis=0)).sum()/(n*(n-1)))
    floor = max(100/np.median(shade[f.idx]), 3*noise_rms, 3*repeat_sem)
    local = np.linalg.norm(signal, axis=1)
    coherent = np.count_nonzero((local > floor) & (signal@vec > local*amp*np.cos(np.pi/4)))
    status = ('below_empirical_gate' if amp <= floor else 'not_repeated' if
              coherent < max(3, np.ceil(.75*n)) else 'resolved')
    return dict(out, status=status, coherent_n=coherent, noise_rms_pct=noise_rms,
                repeat_sem_pct=repeat_sem, gate_semiamp_pct=floor, fit_semiamp_pct=amp)


def free_fit(data):
    v, _ = data
    runs = light_runs(smooth(v[:, 0], 7) < .65)  # original R35 seed mask
    if sum(b-a for a, b in runs) < 3*BAND[0]/2:
        # Short shutters can push even fine troughs below .65. This fallback
        # only proposes a pitch; no unmasked fit is used as a measurement.
        runs = [(0, len(v))]
    seed = LightFit(v, runs).best()
    runs = runs_at(v[:, 0], seed)
    if not runs:
        return assess(data, seed)
    pitch = LightFit(v, runs).best()
    out = assess(data, pitch)
    if out['status'] == 'resolved':
        if min(pitch-BAND[0], BAND[1]-pitch) < .1:
            out['status'] = 'search_edge'
        else:
            out['pitch_raw'] = pitch
    return out


def measure(paths):
    records = []
    for phase, us in PHASES.items():
        found = sorted((n, p) for (k, n), p in paths.items() if k == phase)
        for n, path in found or [(None, None)]:
            if path is not None and n < 1:
                raise ValueError(f'{phase}: expected positive frame index')
            row, data = load(path, us) if path is not None else (dict(gate='missing_phase'), None)
            info = dict(phase=phase, frame_n=n, phase_n=len(found), expected_us=us,
                        roi_y0_y1_x0_x1=':'.join(map(str, ROI)), **row)
            free = free_fit(data) if data is not None else dict(status=row['gate'])
            records.append((info, data, free))
    lock, source = None, None
    for prefix in ('day_offLow_', 'day_off_'):
        for t in ('500', '312', '200', '125'):
            candidates = [f for r, d, f in records if r['phase'] == prefix+t and d is not None]
            ps = [f['pitch_raw'] for f in candidates if f['status'] == 'resolved']
            if len(ps) >= max(2, np.ceil(.75*len(candidates))) and max(ps)/min(ps) <= 1.05:
                lock, source = np.median(ps), prefix+t
                break
        if source:
            break
    if lock is None:
        lock, source = ARCHIVE_PITCH, 'archive_R35_only_no_local_off_reference'
    for row, data, free in records:
        locked = dict(status=row['gate']) if data is None else assess(data, lock)
        yield dict(row, lock_source=source, lock_pitch_raw=lock,
                   **{'free_'+k: v for k, v in free.items()}, **{'locked_'+k: v for k, v in locked.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', metavar='FRAMES', type=Path)
    args = parser.parse_args()
    try:
        rows = list(measure(inputs(args.frames)))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    fields = ('phase frame_n phase_n expected_us exposure_us roi_y0_y1_x0_x1 mean_dn clip_n '
              'floor_n gate lock_source lock_pitch_raw free_pitch_raw').split()
    for prefix in ('free_', 'locked_'):
        fields.extend(prefix+k for k in ('status kept_cells light_runs complete_n longest_n coherent_n '
                                         'fit_semiamp_pct gate_semiamp_pct noise_rms_pct repeat_sem_pct').split())
    writer = csv.DictWriter(sys.stdout, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
