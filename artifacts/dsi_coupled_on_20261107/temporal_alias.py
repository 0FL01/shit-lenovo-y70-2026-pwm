#!/usr/bin/env python3
"""Track the saved q93 spatial component through S0C1; aliases are not PWM Hz."""
import json
import runpy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-coupled-on-20261107')
fit_alias = runpy.run_path(str(ROOT / 'artifacts/stock_base_rates_20261107/temporal_alias.py'))['fit_alias']


def main():
    destination = OUT / 'temporal_alias.json'
    if destination.exists():
        raise FileExistsError(destination)
    analysis = json.loads((OUT / 'analysis_spatial_v2.json').read_text())
    assert [s['label'] for s in analysis['stages']] == ['baseline', 's0c1', 'return_s0c1']
    with np.load(PRIVATE / 'analysis-profiles-spatial-v2.npz', allow_pickle=False) as z:
        profiles, pts = z['profiles'], z['pts_s']
    assert np.all(np.isfinite(profiles)) and np.all(np.diff(pts) > 0)
    t = np.arange(75) / 30
    for alias in (0, 1.3, -5.2):
        slope, residual = fit_alias(np.exp(2j*np.pi*alias*t), t)
        assert abs(slope-alias) < 1e-12 and residual < 1e-12
    q = 1 / 93.43
    y = np.arange(profiles.shape[1])
    x = np.linspace(-1, 1, len(y))
    design = np.array([np.ones(len(y)), x, x*x,
        np.cos(2*np.pi*q/6*y), np.sin(2*np.pi*q/6*y)] +
        [f(2*np.pi*h*q*y) for h in range(1, 5) for f in (np.cos, np.sin)]).T
    stages = []
    for stage in analysis['stages']:
        lo, hi = stage['window_s']
        mask = (pts >= lo) & (pts < hi)
        assert int(mask.sum()) == stage['frames']
        selected = profiles[mask]
        coefficients = np.linalg.lstsq(design, selected.T, rcond=None)[0].T
        components = coefficients[:, 5::2] - 1j*coefficients[:, 6::2]
        harmonics = []
        for h in range(1, 5):
            alias, residual = fit_alias(components[:, h-1], pts[mask])
            harmonics.append({'spatial_harmonic': h,
                'sampled_alias_cycles_per_second': alias,
                'phase_residual_rms_cycles': residual,
                'mean_coefficient_amplitude_Y': float(np.abs(components[:, h-1]).mean())})
        stages.append({'label': stage['label'], 'frames': stage['frames'],
            'window_s': stage['window_s'], 'harmonics': harmonics,
            'model_residual_rms_Y': float(np.sqrt(np.mean((selected-coefficients@design.T)**2)))})
    result = {'method': 'Raw profiles; quadratic plus broad spatial nuisance and four fixed spatial harmonics; no temporal mean removal; complex phase versus video PTS',
        'fixed_spatial_component_cycles_per_row': q,
        'stages': stages, 'synthetic_signed_and_stationary_alias_tests_passed': True,
        'pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False,
        'limits': ['Tracks the original q93 family, not every new spatial component.',
                   'Weak coefficients or poor phase residuals do not establish a stable oscillation.',
                   'Camera cadence aliases remain; spatial harmonic order need not be physical PWM harmonic order.',
                   'Video PTS is not sensor timestamp calibration; no confidence interval for physical Hz.']}
    with destination.open('x') as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
