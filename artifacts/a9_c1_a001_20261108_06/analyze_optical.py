#!/usr/bin/env python3
"""Offline, native-Y optical comparison. Input video stays private; no device I/O.

Usage: .venv/bin/python artifacts/a9_c1_a001_20261108_06/analyze_optical.py VIDEO
       --output NEW.json --profiles NEW.npz
Outputs are exclusive-create. Frequencies are cycles per camera row, never Hz.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from optical_spectrum import analyze_profiles

ROIS = {'main': [260, 70, 40, 540], 'left': [220, 70, 40, 540], 'right': [320, 70, 40, 540]}
BANDS = {'broad': [.002, .006], 'stock_fine': [.015, .025], 'higher': [.025, .1],
         'high_spatial_tail': [.1, .5]}


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def seconds(value):
    return datetime.fromisoformat(value).timestamp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    args = parser.parse_args()
    check(not args.output.exists() and not args.profiles.exists(), 'Refusing to overwrite output')
    run = json.loads((Path(__file__).parent / 'run.json').read_text())
    check(run.get('finished_at_utc') and run.get('error') is None and run.get('series_complete') and run.get('stock_return_verified')
          and run.get('camera_stopped_verified') and run.get('target_restored') and run.get('cleanup_errors') == [],
          'Trial is not complete or clean')
    stages = run['stages']
    check([s['label'] for s in stages] == ['baseline', 'a9_only', 'return_a9_only'], 'Unexpected stage order')
    check(all(s['same_dbv_replay']['dbv'] == 3600 and s['hold_no_native_dsi_writes_verified']
              and s['native_packets_matched'] == 75 for s in stages), 'Missing controlled-state evidence')
    c1 = [s.get('c1_capture', {}) for s in stages]
    check(all(c.get('framing_qualified') and c.get('cleanup_verified') and c.get('native_dbv') == 3600
              for c in c1), 'Missing qualified C1 observations')
    metadata = list(run['recording_preflight']) + [s[k] for s in stages for k in ('camera_start', 'camera_end')]
    offsets = []
    for m in metadata:
        check(m['recording_verified'], 'Recording not qualified')
        check(m['result']['exposure_ns'] == 100000 and m['result']['iso'] == 6400, 'Camera profile mismatch')
        enc = next(s for s in m['streams'] if s['id'] == m['encoder_stream_id'])
        if enc['last_timestamp_ns'] == m['timestamp_ns']:
            offsets.append(m['frame_count'] - enc['frames_produced'])
    check(len(offsets) >= 3 and len(set(offsets)) == 1, 'Inconsistent camera/encoder frame-count mapping')
    count_offset = offsets[0]
    windows = []
    for stage in stages:
        anchors = []
        for side in ('start', 'end'):
            label = '<private ' + stage['label'] + '-' + side + '-camera.txt>'
            events = [e for e in run['events'] if e['stdout'] == label]
            check(len(events) == 1, 'Missing camera event anchor')
            m = stage['camera_' + side]
            anchors.append((seconds(events[0]['at_utc']), m['frame_count'] - count_offset - 1))
        hold_start, hold_end = [seconds(stage[k]) for k in ('hold_start_utc', 'hold_end_utc')]
        center = round(np.interp((hold_start + hold_end) / 2,
                                [a[0] for a in anchors], [a[1] for a in anchors]))
        windows.append({'label': stage['label'], 'frames_start_inclusive': center - 75,
                        'frames_end_exclusive': center + 75,
                        'hold_seconds': hold_end - hold_start,
                        'anchor_implied_frame_rate': (anchors[1][1] - anchors[0][1]) / (anchors[1][0] - anchors[0][0])})
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=codec_name,width,height,pix_fmt,color_range,time_base,nb_frames,duration:frame=best_effort_timestamp_time',
        '-of', 'json', str(args.video)], text=True))
    stream = probe['streams'][0]
    check((stream['width'], stream['height'], stream['pix_fmt'], stream['color_range']) ==
          (1280, 720, 'yuv420p', 'tv'), 'Unexpected original video geometry/range')
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    check(len(pts) == int(stream['nb_frames']) and np.all(np.diff(pts) > 0), 'Invalid decoded frame timestamps')
    select = '+'.join(f"between(n\\,{w['frames_start_inclusive']}\\,{w['frames_end_exclusive']-1})" for w in windows)
    # One decode, no rotation, scaling, gray-range conversion or temporal resampling.
    command = ['ffmpeg', '-v', 'error', '-noautorotate', '-i', str(args.video), '-vf',
               'select=' + select + ',crop=140:540:220:70,extractplanes=y',
               '-fps_mode', 'passthrough', '-enc_time_base', 'demux', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    raw = subprocess.check_output(command)
    check(len(raw) == 450 * 540 * 140, 'Unexpected selected native-Y byte count')
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(3, 150, 540, 140)
    profiles = {name: frames[:, :, :, x-220:x-220+w].mean(axis=3)
                for name, (x, y, w, h) in ROIS.items()}
    main_spectra = [analyze_profiles(p, n_fft=8192, frequency_min=0, frequency_max=.5)
                    for p in profiles['main']]
    q = main_spectra[0]['frequencies_cycles_per_row']
    fine_indices = np.flatnonzero((q >= .015) & (q <= .025))
    stock_power = (main_spectra[0]['total_power'] + main_spectra[2]['total_power']) / 2
    fine_index = fine_indices[np.argmax(stock_power[fine_indices])]
    fixed_fine = float(q[fine_index])
    # A conditional spatial submultiple, not an asserted physical fundamental.
    fixed_broad = fixed_fine / 6
    qs = [fixed_broad, fixed_fine / 2, fixed_fine, fixed_fine * 2, fixed_fine * 3]
    measurements = []
    for roi, profile_stages in profiles.items():
        for stage_index, p in enumerate(profile_stages):
            pix = frames[stage_index, :, :, ROIS[roi][0]-220:ROIS[roi][0]-220+40]
            entry = {'stage': windows[stage_index]['label'], 'roi': roi,
                     'mean_y': float(p.mean()), 'min_y': int(pix.min()), 'max_y': int(pix.max()),
                     'fraction_y_ge_235': float(np.mean(pix >= 235)),
                     'fraction_y_le_16': float(np.mean(pix <= 16)), 'degrees': {}}
            check(p.mean() > 16, 'Insufficient positive mean signal for image-code normalization')
            for degree in (None, 1, 2, 3):
                spectrum = analyze_profiles(p, n_fft=8192, frequency_min=0,
                                            frequency_max=.5, detrend_degree=degree, peak_count=12)
                fixed = analyze_profiles(p, frequencies=qs, detrend_degree=degree)
                check(spectrum['power_partition_max_abs_error'] < 1e-10, 'Power decomposition failed')
                row = {'fixed_total_rms_y': fixed['total_rms_amplitude'].tolist(),
                       'fixed_coherent_y': fixed['coherent_amplitude'].tolist(),
                       'fixed_incoherent_rms_y': fixed['incoherent_rms_amplitude'].tolist(),
                       'fixed_normalized_rms': (fixed['total_rms_amplitude'] / (p.mean()-16)).tolist(),
                       'peaks': spectrum['peaks'], 'bands': {}}
                for name, (lo, hi) in BANDS.items():
                    inds = np.flatnonzero((spectrum['frequencies_cycles_per_row'] >= lo) &
                                         (spectrum['frequencies_cycles_per_row'] <= hi))
                    i = inds[np.argmax(spectrum['total_power'][inds])]
                    row['bands'][name] = {'period_rows': float(1/spectrum['frequencies_cycles_per_row'][i]),
                                         'rms_y': float(spectrum['total_rms_amplitude'][i]),
                                         'normalized_rms': float(spectrum['total_rms_amplitude'][i]/(p.mean()-16)),
                                         'at_band_edge': bool(i in (inds[0], inds[-1]))}
                entry['degrees'][str(degree)] = row
            entry['nonoverlapping_50_frame_blocks'] = []
            central = p[30:120]
            central_fixed = analyze_profiles(central, frequencies=qs)
            entry['primary_central_90_frames'] = {
                'mean_y': float(central.mean()),
                'fixed_total_rms_y': central_fixed['total_rms_amplitude'].tolist(),
                'fixed_coherent_y': central_fixed['coherent_amplitude'].tolist(),
                'fixed_incoherent_rms_y': central_fixed['incoherent_rms_amplitude'].tolist(),
                'fixed_normalized_rms': (central_fixed['total_rms_amplitude']/(central.mean()-16)).tolist()}
            for start in (0, 50, 100):
                block = p[start:start+50]
                fixed = analyze_profiles(block, frequencies=qs)
                entry['nonoverlapping_50_frame_blocks'].append({
                    'offset_start': start, 'mean_y': float(block.mean()),
                    'fixed_normalized_rms': (fixed['total_rms_amplitude']/(block.mean()-16)).tolist()})
            measurements.append(entry)
    ratios = []
    primary_ratios = []
    for roi in ROIS:
        selected = [e for e in measurements if e['roi'] == roi]
        a, b, c = [np.array(e['primary_central_90_frames']['fixed_normalized_rms']) for e in selected]
        primary_ratios.append({'roi': roi, 'candidate_over_adjacent_stock_mean': (b/((a+c)/2)).tolist(),
                               'return_over_baseline': (c/a).tolist()})
        for degree in ('None', '1', '2', '3'):
            a, b, c = [np.array(e['degrees'][degree]['fixed_normalized_rms']) for e in selected]
            ratios.append({'roi': roi, 'detrend_degree': degree,
                           'candidate_over_adjacent_stock_mean': (b/((a+c)/2)).tolist(),
                           'return_over_baseline': (c/a).tolist()})
    for window in windows:
        a, b = window['frames_start_inclusive'], window['frames_end_exclusive']
        window['pts_first_seconds'] = float(pts[a]); window['pts_last_seconds'] = float(pts[b-1])
        window['primary_frames_start_inclusive'] = a + 30
        window['primary_frames_end_exclusive'] = b - 30
    result = {'source_run': 'run.json', 'source_video': 'Private original A9 plus C1 readback A001 recording, series 06',
              'source_video_bytes': args.video.stat().st_size, 'stream': stream,
              'decoded_pts_strictly_increasing': True, 'decoded_frame_count': len(pts),
              'rois_xywh': ROIS, 'windows': windows,
              'alignment': 'Interpolate host dump-completion UTC vs camera frame counts at both hold ends. Host calls have latency: the nominal approximately 1 second margin for 150 frames is not guaranteed. Primary 90 central frames add 1 second at each edge; 150 frames and 50-frame blocks are sensitivity checks. Counts are consistent across snapshots; no per-frame exposure-to-MP4 binding is claimed.',
              'roi_selection': 'Chosen after native-frame inspection: left interior, away from screen borders/right-side text. Left/right are sensitivity controls, not independent experiments.',
              'fixed_q_cycles_per_row': qs, 'fixed_stock_fine_period_rows': 1/fixed_fine,
              'fixed_broad_note': 'Fine/6 is a diagnostic spatial submultiple, not a physical-frequency assignment.',
              'normalization': 'RMS camera Y coefficient divided by mean(Y)-16; code-value metric, not optical modulation depth.',
              'detrend': 'Per-frame spatial only; temporal mean is never removed. None/1/2/3 sensitivity retained.',
              'full_spectral_range_cycles_per_row': [0, .5],
              'measurements': measurements, 'ratios': ratios, 'primary_central_90_frame_ratios': primary_ratios,
              'c1_observations': [{'stage': stage['label'], 'data': capture['data'],
                                   'native_dbv': capture['native_dbv'],
                                   'software_refresh': capture['software_refresh']}
                                  for stage, capture in zip(stages, c1)],
              'c1_limit': 'Temporal association with image changes only; C1 values are not assigned physical PWM Hz.',
              'physical_pwm_hz': None,
              'limits': ['Single stock/candidate/stock series, not independent replication.',
                         'Encoded Y includes ISP/codec, black-level and nonlinear response.',
                         'Only about 1.8 broad periods fit the ROI; broad peak depends on detrending.',
                         'No calibrated row time, fundamental-frequency proof, envelope clearance, or comfort result.']}
    prior_path = ROOT / 'artifacts/a9_a001_20261108_01/optical_analysis_v2.json'
    if prior_path.exists():
        prior = json.loads(prior_path.read_text())
        previous_ratio = next(r for r in prior['primary_central_90_frame_ratios'] if r['roi'] == 'main')
        current_ratio = next(r for r in primary_ratios if r['roi'] == 'main')
        result['prior_series_01_comparison'] = {
            'source': 'artifacts/a9_a001_20261108_01/optical_analysis_v2.json',
            'previous_stock_fine_period_rows': prior['fixed_stock_fine_period_rows'],
            'current_stock_fine_period_rows': result['fixed_stock_fine_period_rows'],
            'previous_primary_fine_ratio': previous_ratio['candidate_over_adjacent_stock_mean'][2],
            'current_primary_fine_ratio': current_ratio['candidate_over_adjacent_stock_mean'][2],
            'limit': 'Each ratio uses its own same-video stock controls and freshly selected stock peak; not a cross-session optical calibration.'}
    arrays = {'profiles_'+k: v for k, v in profiles.items()}
    arrays.update(q=q, pts=pts)
    for index, spectrum in enumerate(main_spectra):
        for field in ('total_power', 'coherent_power', 'incoherent_power'):
            arrays[f'{windows[index]["label"]}_{field}'] = spectrum[field]
    # Use explicit exclusive modes even under python -O.
    with args.profiles.open('xb') as handle:
        np.savez_compressed(handle, **arrays)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False); handle.write('\n')
    for entry in measurements:
        if entry['roi'] == 'main':
            print(entry['stage'], entry['mean_y'], entry['degrees']['2']['fixed_normalized_rms'])
    print('Outputs written; physical_pwm_hz remains null.')


if __name__ == '__main__':
    main()
