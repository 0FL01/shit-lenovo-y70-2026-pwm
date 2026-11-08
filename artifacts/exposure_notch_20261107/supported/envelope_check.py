#!/usr/bin/env python3
"""Offline detrend sensitivity of broad/fine spatial bands in saved stock footage.

No device calls, new exposures, PWM-frequency inference, or rewrite of the
original optical analysis. Input profiles were decoded and saved by ../analyze.py.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '06-tools'))
from optical_spectrum import analyze_profiles

HERE = Path(__file__).resolve().parent
PROFILES = Path('/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported/profiles.npz')
BANDS = {'broad': (0.0023, 0.0037), 'fine': (0.0097, 0.0119)}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def analyze():
    archived = json.loads((HERE / 'analysis.json').read_text())
    with np.load(PROFILES, allow_pickle=False) as saved:
        check(set(saved.files) == {'profiles', 'pts_s', 'roi_xywh'}, 'Unexpected profile fields')
        profiles, pts = saved['profiles'], saved['pts_s']
        check(saved['roi_xywh'].tolist() == archived['roi_xywh'], 'ROI differs from original')
    check(profiles.shape == (archived['decoded_frames'], 500), 'Unexpected source shape')
    check(len(archived['stages']) == 6 and np.all(np.diff(pts) > 0), 'Invalid stages/PTS')
    by_degree = {}
    for degree in (0, 1, 2, 3):
        stages = []
        for original in archived['stages']:
            lo, hi = original['window_s']
            subset = profiles[(pts >= lo) & (pts < hi)]
            check(len(subset) == original['frames'] == 75, 'Window differs from original')
            spectrum = analyze_profiles(subset, n_fft=16384, peak_count=0,
                                        detrend_degree=degree)
            mean = spectrum['raw_mean'] - 16
            check(abs(spectrum['raw_mean']-original['raw_mean_Y']) < 1e-12, 'Mean differs from original')
            check(mean > 0 and spectrum['power_partition_max_abs_error'] < 1e-10,
                  'Invalid mean/power partition')
            grid, power, coherent = (spectrum[k] for k in
                                     ('frequencies_cycles_per_row', 'total_power', 'coherent_power'))
            row = {'phase': original['phase'], 'exposure_us': original['exposure_ns']/1000,
                   'bands': {}}
            for name, (low, high) in BANDS.items():
                indices = np.flatnonzero((grid >= low) & (grid <= high))
                check(len(indices) > 2, 'Band has insufficient spectral samples')
                idx = indices[np.argmax(power[indices])]
                row['bands'][name] = {
                    'peak_cycles_per_row': float(grid[idx]),
                    'maximum_rms_over_meanY_minus16': float(np.sqrt(power[idx])/mean),
                    'coherent_fraction_of_peak_power': float(coherent[idx]/power[idx]),
                    'at_selected_band_boundary': bool(idx in (indices[0], indices[-1]))}
            stages.append(row)
        check([r['phase'] for r in stages] == [1, 2, 3, 4, 5, 6], 'Unexpected stage order')
        baseline = {name: (stages[0]['bands'][name]['maximum_rms_over_meanY_minus16']
                           + stages[-1]['bands'][name]['maximum_rms_over_meanY_minus16'])/2
                    for name in BANDS}
        for row in stages:
            for name in BANDS:
                row['bands'][name]['ratio_to_bracketing_100us'] = (
                    row['bands'][name]['maximum_rms_over_meanY_minus16']/baseline[name])
        by_degree[str(degree)] = stages
    fine_at_notch = [by_degree[str(k)][3]['bands']['fine']['ratio_to_bracketing_100us'] for k in range(4)]
    broad_at_notch = [by_degree[str(k)][3]['bands']['broad']['ratio_to_bracketing_100us'] for k in range(4)]
    return {'source': str(PROFILES), 'original_analysis': str(HERE/'analysis.json'),
            'scope': 'Saved 6x75-frame stock windows; spatial band/detrend sensitivity, NOT optical Hz',
            'band_ranges_cycles_per_camera_row': BANDS,
            'broad_span_cycles_across_500_rows': [0.0023*500, 0.0037*500],
            'detrend_degrees': by_degree,
            'notch_phase4_fine_ratios_by_degree0to3': fine_at_notch,
            'notch_phase4_broad_ratios_by_degree0to3': broad_at_notch,
            'interpretation_limits': ['<2 broad-band spatial cycles across the cropped 500 rows: susceptible to scene gradient and polynomial detrend',
                                      'Coherent band can be static image structure or camera artifacts',
                                      'No camera code->luminance calibration; temporal envelope and physical PWM frequency are not identified',
                                      'The 1.428571ms exposure is near, not at, the ideal integer-period zero at 1.388889ms for 720/1440/2160Hz'],
            'physical_pwm_hz': None, 'new_device_io': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = analyze()
    with args.output.open('x') as out:
        out.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print('PASS: saved 6×75 windows, 4 detrend choices, two optical bands; no Hz inference')
