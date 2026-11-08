#!/usr/bin/env python3
"""Same-video phase diagnostic: sampled aliases, never physical PWM Hz."""
import json
from pathlib import Path

import numpy as np


def fit_alias(coefficients, pts):
    t = np.asarray(pts) - np.mean(pts)
    phase = np.unwrap(np.angle(coefficients)) / (2 * np.pi)
    slope, intercept = np.polyfit(t, phase, 1)
    return float(slope), float(np.std(phase - (slope*t + intercept)))


def main():
    out = Path(__file__).resolve().parent
    assert not (out / 'temporal_alias.json').exists()
    analysis = json.loads((out / 'analysis.json').read_text())
    with np.load('/home/stfu/.cache/opencode-tmp/opencode/stock-base-rates-20261107/profiles.npz', allow_pickle=False) as z:
        profiles, pts = z['profiles'], z['pts_s']
    t = np.arange(75) / 30
    for alias in (0, 1.3, -5.2):
        slope, residual = fit_alias(np.exp(2j*np.pi*alias*t), t)
        assert abs(slope-alias) < 1e-12 and residual < 1e-12
    stages = []
    for stage in analysis['stages']:
        lo, hi = stage['window_s']
        mask = (pts >= lo) & (pts < hi)
        selected = profiles[mask]
        # Existing spatial harmonic train supplies q; this is not a Hz mapping.
        q = np.mean([stage['peaks'][h-1]['frequency_cycles_per_row']/h for h in (3, 4)])
        y = np.arange(selected.shape[1])
        x = np.linspace(-1, 1, len(y))
        design = np.array([np.ones(len(y)), x, x*x,
            np.cos(2*np.pi*q/6*y), np.sin(2*np.pi*q/6*y)] +
            [f(2*np.pi*h*q*y) for h in range(1, 5) for f in (np.cos, np.sin)]).T
        coeff = np.linalg.lstsq(design, selected.T, rcond=None)[0].T
        complex_coeff = coeff[:, 5::2] - 1j*coeff[:, 6::2]
        harmonics = []
        for h in range(1, 5):
            alias, residual = fit_alias(complex_coeff[:, h-1], pts[mask])
            harmonics.append({'spatial_harmonic': h, 'sampled_alias_cycles_per_second': alias,
                              'phase_residual_rms_cycles': residual})
        stages.append({'phase': stage['phase'], 'requested_refresh': stage['requested_refresh'],
                       'spatial_train_cycles_per_row': float(q), 'harmonics': harmonics})
    result = {'method': 'Raw profiles, polynomial+broad spatial nuisance and four spatial harmonics; no temporal mean subtraction; unwrapped complex phase vs video PTS',
        'stages': stages, 'synthetic_signed_and_stationary_alias_tests_passed': True,
        'pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False,
        'interpretation': 'Same approximate sampled alias (~1.3 cycles/s) across base modes is compatible with a shared carrier and changed spatial scan phase, but also with carriers separated by integer multiples of camera cadence.',
        'limits': ['30fps temporal alias branches remain; sign follows the chosen spatial complex component.',
                   'Spatial harmonic number is not established as physical PWM harmonic number.',
                   'Video PTS is not per-frame sensor timestamp calibration; reported residuals are not physical-Hz confidence intervals.',
                   'Spatial peak interpolation and model nuisance choices are not calibrated metrology.']}
    with (out / 'temporal_alias.json').open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
