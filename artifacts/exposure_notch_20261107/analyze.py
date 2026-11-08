#!/usr/bin/env python3
"""Offline supported-exposure notch analysis; does not identify physical PWM Hz."""
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
from optical_spectrum import analyze_profiles

OUT = Path(__file__).resolve().parent / 'supported'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107-supported')
MARKER = 'PWM_NOTCH_SUPPORTED'
PATTERN = r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)'


def writes(text):
    return [(int(n), int(k, 16), mode, bytes.fromhex(payload))
            for n, k, mode, payload in re.findall(PATTERN, text)]


def main():
    assert not (OUT / 'analysis.json').exists(), 'Preserve previous analysis'
    r = json.loads((OUT / 'run.json').read_text())
    assert r['six_conditions_complete'] and r['target_restored'] and r['camera_stopped_verified']
    assert not r['cleanup_errors'] and 'error' not in r
    assert len(r['phases']) == 6
    for k, v in [('android.sensor.exposureTime', '100000'), ('android.sensor.sensitivity', '6400')]:
        assert r['camera_restored_metadata'][k] == [v]*2
    native = []
    for p in r['phases']:
        i = p['index']
        assert p['dc'] == 0 and p['dbv'] == 3600 and p['requested_refresh'] == 120
        assert abs(p['software_refresh_end'] - 120) < .02
        assert abs(p['exposure_ns'] - p['requested_exposure_ns']) <= .05*p['requested_exposure_ns']
        text = (PRIVATE / f'phase-{i}-kernel.txt').read_text()
        assert 'Command transfer failed' not in text[text.index(MARKER + '_BEGIN'):]
        section = text[text.index(f'{MARKER}_PHASE_{i}_0'):]
        before, hold = section.split(f'{MARKER}_HOLD_{i}', 1)
        hold = hold.split(f'{MARKER}_END_HOLD_{i}', 1)[0]
        assert writes(before) == [(3, 0x39, 'hs', bytes.fromhex('51 0e 10'))]
        assert not writes(hold)
        native.append({'phase': i, 'standard_same_dbv_writes': 1, 'hold_writes': 0})
        for label in ('camera_start', 'camera_end'):
            c = p[label]
            assert c['android.sensor.exposureTime'] == [str(p['exposure_ns'])]*2
            assert c['android.sensor.sensitivity'] == ['1600']*2
            for key in ('android.control.aeMode', 'android.control.afMode',
                        'android.control.videoStabilizationMode', 'android.lens.opticalStabilizationMode'):
                assert c[key] == ['OFF']*2
            for key in ('android.lens.focusDistance', 'android.sensor.rollingShutterSkew',
                        'android.scaler.cropRegion', 'android.control.zoomRatio'):
                assert c[key] == r['phases'][0]['camera_start'][key]
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
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_streams', '-show_frames', '-show_entries',
        'stream=width,height,nb_frames:frame=best_effort_timestamp_time', '-of', 'json', str(video)], text=True))
    stream = probe['streams'][0]
    assert (stream['width'], stream['height']) == (1280, 720)
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    pts -= pts[0]
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
        'crop=w=60:h=500:x=540:y=190:exact=1,extractplanes=y', '-fps_mode', 'passthrough',
        '-enc_time_base', 'demux',
        '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 500, 60)
    assert len(pixels) == len(pts) == int(stream['nb_frames'])
    profiles = pixels.mean(axis=2)
    with (PRIVATE / 'profiles.npz').open('xb') as f:
        np.savez_compressed(f, profiles=profiles, pts_s=pts, roi_xywh=[540, 190, 60, 500])
    (PRIVATE / 'profiles.npz').chmod(0o600)
    # Only the recorder-start tap comes after this marker; earlier taps set ISO/shutter.
    media_index = next(i for i, e in enumerate(r['events']) if e['command'] == f"printf '<6>{MARKER}_BEGIN\n' > /dev/kmsg")
    start_tap = next(e for e in r['events'][media_index:] if e['device'] == 'camera' and e['command'].startswith('input tap '))
    origin = datetime.fromisoformat(start_tap['at_utc'])
    sheet = Image.new('RGB', (1920, 792), '#202020')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    stages = []
    for p in r['phases']:
        lo, hi = [datetime.fromisoformat(p[k]) for k in ('hold_start_utc', 'hold_end_utc')]
        assert 7 <= (hi-lo).total_seconds() < 8
        center = ((lo-origin).total_seconds() + (hi-origin).total_seconds())/2
        mask = (pts >= center-1.25) & (pts < center+1.25)
        assert mask.sum() >= 70
        spectrum = analyze_profiles(profiles[mask], n_fft=16384)
        reference = analyze_profiles(profiles[mask], frequencies=np.arange(1, 5)/93.43)
        with (OUT / f'phase-{p["index"]}-spectrum.npz').open('xb') as f:
            np.savez_compressed(f, **{k: spectrum[k] for k in ('frequencies_cycles_per_row',
                'total_power', 'coherent_power', 'incoherent_power', 'raw_mean_per_frame')})
        mean = spectrum['raw_mean'] - 16
        assert mean > 0
        stages.append({'phase': p['index'], 'exposure_ns': p['exposure_ns'], 'iso': 1600,
            'window_s': [center-1.25, center+1.25], 'frames': int(mask.sum()),
            'raw_mean_Y': spectrum['raw_mean'], 'mean_Y_minus16': mean,
            'fraction_Y_ge235': float(np.mean(pixels[mask] >= 235)),
            'reference_period_rows': 93.43,
            'q_harmonic_total_amplitudes': reference['total_rms_amplitude'].tolist(),
            'q_harmonic_coherent_amplitudes': reference['coherent_amplitude'].tolist(),
            'q_harmonic_incoherent_amplitudes': reference['incoherent_rms_amplitude'].tolist(),
            'normalized_q_harmonics': (reference['total_rms_amplitude']/mean).tolist(),
            'peaks': spectrum['peaks'], 'power_partition_error': spectrum['power_partition_max_abs_error']})
        rgb = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(center), '-i', str(video),
            '-frames:v', '1', '-vf', 'eq=gamma=2,scale=640:360', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
        x, y = (p['index']-1) % 3*640, (p['index']-1)//3*396
        sheet.paste(Image.frombytes('RGB', (640, 360), rgb), (x, y+36))
        draw.text((x+8, y+8), f'{p["index"]}: {p["exposure_ns"]/1000:.1f}us ISO1600 | {center:.2f}s', font=font, fill='white')
    baseline = (np.array(stages[0]['normalized_q_harmonics']) + stages[-1]['normalized_q_harmonics'])/2
    for s in stages:
        s['normalized_harmonic_ratios_to_bracketing_100us'] = (np.array(s['normalized_q_harmonics'])/baseline).tolist()
    with (OUT / 'comparison.png').open('xb') as f:
        sheet.save(f, format='PNG')
    result = {'method': 'Spatial-v2, no temporal demeaning; total/coherent/incoherent spectra, same ROI; Y-minus16 ratios are camera-code metrics, not luminance calibration',
        'video': r['video'], 'video_bytes': r['video_bytes'], 'decoded_frames': len(pts),
        'roi_xywh': [540, 190, 60, 500], 'stages': stages,
        'native': {'phases': native, 'controller_returns': len(returns), 'negative_returns': 0, 'probe_misses': 0},
        'camera_restored': True, 'target_restored': True, 'pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False,
        'idealized_predictions_only': {str(hz): [float(abs(np.sinc(hz*s['exposure_ns']*1e-9))/abs(np.sinc(hz*1e-4))) for s in stages]
                                       for hz in (720, 1440, 2160)},
        'limits': ['Integration model assumes a stable periodic component and linear temporal exposure, not calibrated ISP photometry.',
            'A minimum may be an integer-period notch; harmonic order and fundamental remain to be distinguished.',
            'Video code scaling/black level/noise/static UI and spatial detrending can bias normalized amplitudes.',
            'Record-tap alignment is coarse; inspect central frames rather than claiming sensor timestamps.',
            'This changes camera integration only, not panel PWM or the owner frequency requirement.']}
    with (OUT / 'analysis.json').open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'native': result['native'], 'decoded_frames': len(pts), 'stages': [
        {k: v for k, v in s.items() if k != 'peaks'} for s in stages],
        'idealized_predictions_only': result['idealized_predictions_only']}, indent=2))


if __name__ == '__main__':
    main()
