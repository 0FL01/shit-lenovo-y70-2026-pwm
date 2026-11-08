#!/usr/bin/env python3
"""Offline validation of the one-shot stock base-rate optical control."""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from audit_pwm_archive import parse_packets
from optical_spectrum import analyze_profiles

OUT = Path(__file__).resolve().parent
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/stock-base-rates-20261107')
PATTERN = r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)'


def writes(text):
    return [(int(n), int(k, 16), mode, bytes.fromhex(data))
            for n, k, mode, data in re.findall(PATTERN, text)]


def main():
    assert not (OUT / 'analysis.json').exists(), 'Preserve existing evidence'
    r = json.loads((OUT / 'run.json').read_text())
    assert r['five_conditions_complete'] and r['target_restored']
    assert r['camera_stopped_verified'] and not r['cleanup_errors'] and 'error' not in r
    assert [p['requested_refresh'] for p in r['phases']] == [120, 144, 120, 90, 120]
    dt = ROOT / 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings'
    timings = {}
    for i in (0, 1, 2, 7):
        path = dt / f'timing@{i}'
        assert (path / 'qcom,mdss-dsi-timing-switch-command-state').read_bytes().rstrip(b'\0') == b'dsi_lp_mode'
        timings[i] = [(len(bytes.fromhex(p['payload'])), bytes.fromhex(p['header'])[0], 'lp', bytes.fromhex(p['payload']))
                      for p in parse_packets((path / 'qcom,mdss-dsi-timing-switch-command').read_bytes())]
    previous = Path('/home/stfu/.cache/opencode-tmp/opencode/ddic-timing-history-20261107/phase-4-kernel.txt').read_text()
    pps_records = {row for row in writes(previous) if row[:3] == (128, 0x0a, 'lp')}
    assert len(pps_records) == 1
    pps = pps_records.pop()
    dbv = [(3, 0x39, 'hs', bytes.fromhex('51 0e 10'))]
    expected = [dbv, timings[1] + dbv * 2, timings[0] + dbv * 2,
                [pps] + timings[7] + dbv + timings[2] + dbv * 2, timings[0] + dbv * 2]
    native = []
    for phase, program in zip(r['phases'], expected):
        i = phase['index']
        text = (PRIVATE / f'phase-{i}-kernel.txt').read_text()
        assert 'Command transfer failed' not in text[text.index('PWM_BASE_REF_BEGIN'):]
        section = text[text.index(f'PWM_BASE_REF_PHASE_{i}_0'):]
        before, hold = section.split(f'PWM_BASE_REF_HOLD_{i}', 1)
        hold = hold.split(f'PWM_BASE_REF_END_HOLD_{i}', 1)[0]
        assert writes(before) == program and not writes(hold)
        assert phase['dbv'] == 3600 and phase['dc'] == 0 and phase['redraw_completed']
        assert abs(phase['software_refresh_end'] - phase['requested_refresh']) < .02
        native.append({'phase': i, 'matched_write_packets': len(program), 'hold_write_packets': 0})
    trace = (PRIVATE / 'trace-final.txt').read_text()
    assert 'LOST' not in trace
    returns = [int(v) for v in re.findall(r'\bctrl_return:.*?rc=(-?\d+)', trace)]
    assert returns and min(returns) >= 0
    profile = (PRIVATE / 'probe-profile.txt').read_text()
    for name in ('ctrl_return', 'param_entry', 'param_return', 'pcd_entry'):
        rows = re.findall(r'^\s*' + name + r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
        assert len(rows) == 1 and int(rows[0][1]) == 0
        assert int(rows[0][0]) == len(re.findall(r'\b' + name + ':', trace))

    video = ROOT / r['video']
    assert video.stat().st_size == r['video_bytes']
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_frames',
        '-show_entries', 'stream=width,height,nb_frames:frame=best_effort_timestamp_time',
        '-of', 'json', str(video)], text=True))
    stream = probe['streams'][0]
    assert (stream['width'], stream['height']) == (1280, 720)
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    pts -= pts[0]
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
        'crop=w=60:h=500:x=540:y=190:exact=1,extractplanes=y', '-fps_mode', 'passthrough',
        '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 500, 60)
    assert len(pixels) == len(pts) == int(stream['nb_frames'])
    profiles = pixels.mean(axis=2)
    with (PRIVATE / 'profiles.npz').open('xb') as f:
        np.savez_compressed(f, profiles=profiles, pts_s=pts, roi_xywh=[540, 190, 60, 500])
    (PRIVATE / 'profiles.npz').chmod(0o600)
    taps = [e for e in r['events'] if e['device'] == 'camera' and e['command'].startswith('input tap ')]
    origin = datetime.fromisoformat(taps[0]['at_utc'])
    sheet = Image.new('RGB', (1920, 792), '#202020')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    results = []
    for phase in r['phases']:
        i = phase['index']
        lo, hi = [datetime.fromisoformat(phase[k]) for k in ('hold_start_utc', 'hold_end_utc')]
        assert 7 <= (hi - lo).total_seconds() < 8
        center = ((lo - origin).total_seconds() + (hi - origin).total_seconds()) / 2
        mask = (pts >= center - 1.25) & (pts < center + 1.25)
        assert mask.sum() >= 70
        for name in ('camera_start', 'camera_end'):
            c = phase[name]
            assert c['android.sensor.exposureTime'] == ['100000'] * 2
            assert c['android.sensor.sensitivity'] == ['6400'] * 2
            for key in ('android.control.aeMode', 'android.control.afMode',
                        'android.control.videoStabilizationMode', 'android.lens.opticalStabilizationMode'):
                assert c[key] == ['OFF'] * 2
            for key in ('android.lens.focusDistance', 'android.sensor.rollingShutterSkew',
                        'android.scaler.cropRegion', 'android.control.zoomRatio'):
                assert c[key] == r['phases'][0]['camera_start'][key]
        selected = profiles[mask]
        spectrum = analyze_profiles(selected, n_fft=16384)
        with (OUT / f'phase-{i}-spectrum.npz').open('xb') as f:
            np.savez_compressed(f, **{key: spectrum[key] for key in (
                'frequencies_cycles_per_row', 'total_power', 'coherent_power',
                'incoherent_power', 'raw_mean_per_frame')})
        ref = analyze_profiles(selected, frequencies=[1/93.43])
        results.append({'phase': i, 'label': f'{i}_{phase["requested_refresh"]}',
            'requested_refresh': phase['requested_refresh'], 'window_s': [center-1.25, center+1.25],
            'frames': int(mask.sum()), 'raw_mean_Y': spectrum['raw_mean'],
            'q93_total_amplitude': float(ref['total_rms_amplitude'][0]),
            'peaks': spectrum['peaks'], 'power_partition_error': spectrum['power_partition_max_abs_error'],
            'fraction_Y_ge235': float(np.mean(pixels[mask] >= 235))})
        rgb = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(center), '-i', str(video),
            '-frames:v', '1', '-vf', 'eq=gamma=2,scale=640:360', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
        x, y = (i-1) % 3 * 640, (i-1) // 3 * 396
        sheet.paste(Image.frombytes('RGB', (640, 360), rgb), (x, y+36))
        draw.text((x+8, y+8), f'{i}: stock {phase["requested_refresh"]} | {center:.2f}s', font=font, fill='white')
    with (OUT / 'comparison.png').open('xb') as f:
        sheet.save(f, format='PNG')
    result = {'status': 'confirmed-on-target', 'method': 'Offline spatial-v2; original limited-range Y, quadratic spatial detrend, Hann, no temporal mean removal',
        'video': r['video'], 'video_bytes': r['video_bytes'], 'decoded_frames': len(pts),
        'roi_xywh': [540, 190, 60, 500], 'stages': results,
        'native': {'phases': native, 'timing_packets': 62, 'same_dbv_writes': 10,
                   'pps_packets': 1, 'pps_equal_prior_stock_transition': True,
                   'controller_returns': len(returns), 'negative_returns': 0, 'probe_misses': 0},
        'target_restored': True, 'pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False,
        'limits': ['Record-tap alignment is coarse; central windows and comparison frames must be inspected.',
            'Camera pixel periods mix source time modulation and spatial panel scan phase, not physical Hz.',
            'Static UI and spatial detrending can bias peaks; no calibrated optical amplitude/envelope.',
            'Zero padding interpolates; it does not improve the physical frequency resolution.',
            'Same DBV is not a photometric brightness calibration.']}
    with (OUT / 'analysis.json').open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
