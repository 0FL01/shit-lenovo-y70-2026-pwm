#!/usr/bin/env python3
"""Offline analysis of the fixed nine-stage corrected-method capture; no ADB."""

import json
import re
import runpy
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from optical_spectrum import analyze_profiles


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/dsi_block_trials_20261106/with_redraw'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-block-trials-20261106-redraw')
LABELS = ['baseline', 'mode90', 'return_mode90', 'thresholds', 'return_thresholds',
          'page53', 'return_page53', 'page63', 'return_page63']


def main():
    report = json.loads((OUT / 'run.json').read_text())
    assert report['series_complete'] and report['stock_return_verified']
    assert report['target_restored'] and not report['cleanup_errors']
    assert report['candidate_attempts_by_name'] == dict.fromkeys(LABELS[1::2], 1)
    assert [s['label'] for s in report['stages']] == LABELS
    assert not (OUT / 'analysis_spatial_v2.json').exists(), 'Do not overwrite v2 analyzed evidence'
    video = ROOT / report['video']
    assert video.stat().st_size == report['video_bytes']
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams',
        '-show_frames', '-show_entries',
        'stream=width,height,nb_frames,avg_frame_rate,duration:frame=best_effort_timestamp_time',
        '-of', 'json', str(video)], text=True))
    stream = probe['streams'][0]
    assert (stream['width'], stream['height']) == (1280, 720)
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    pts -= pts[0]
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(video), '-vf',
        'crop=w=60:h=500:x=540:y=190:exact=1,extractplanes=y',
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 500, 60)
    assert len(pixels) == len(pts) == int(stream['nb_frames'])
    profiles = pixels.mean(axis=2)
    cache = PRIVATE / 'analysis-profiles-spatial-v2.npz'
    np.savez_compressed(cache, pts_s=pts, profiles=profiles, roi_xywh=[540, 190, 60, 500])
    cache.chmod(0o600)

    # The native record tap is a coarse origin, not a sensor timestamp. Central
    # 2.5s windows leave2.25s margins inside each7s hold; inspect frames separately.
    taps = [e for e in report['events'] if e['device'] == 'camera'
            and e['command'].startswith('input tap ')]
    origin = datetime.fromisoformat(taps[0]['at_utc'])
    parser = runpy.run_path(str(ROOT / '06-tools/inspect_cn_dtbo.py'))['packets']
    stock = (ROOT / 'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-dc-off-command').read_bytes()
    programs = {'stock': stock, 'mode90': (ROOT / 'artifacts/dsi_mode_trial_20261106/dc_off_mode90.bin').read_bytes()}
    for name in ('thresholds', 'page53', 'page63'):
        programs[name] = (ROOT / 'artifacts/dsi_block_trials_20261106' / (name + '.bin')).read_bytes()
    packet_pattern = r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)'
    marker = 'PWM_BLOCK_REDRAW'
    results = []
    sheet = Image.new('RGB', (1920, 1188), '#202020')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    matched = 0
    for index, stage in enumerate(report['stages']):
        label = stage['label']
        assert stage['chunks_verified'] == 5 and stage['native_packets_matched'] == 75
        assert stage['redraw_completed'] and stage['same_dbv_replay']['dbv'] == 3600
        for key in ('camera_start', 'camera_end'):
            metadata = stage[key]
            assert metadata['android.sensor.exposureTime'] == ['100000']*2
            assert metadata['android.sensor.sensitivity'] == ['6400']*2
            assert metadata['android.control.aeMode'] == metadata['android.control.afMode'] == ['OFF']*2
            assert all(abs(float(v)-9.11752701) < .001 for v in metadata['android.lens.focusDistance'])
        text = (PRIVATE / (label + '-kernel.txt')).read_text()
        begin = text.index(marker + '_BEGIN_' + label)
        end = text.index(marker + '_END_' + label, begin)
        assert 'Command transfer failed' not in text[begin:]
        records = [(int(n), int(k, 16), mode, bytes.fromhex(payload))
                   for n, k, mode, payload in re.findall(packet_pattern, text[begin:end])]
        name = label if label in programs else 'stock'
        expected = [(len(bytes.fromhex(p['payload_hex'])), bytes.fromhex(p['header_hex'])[0],
                     'hs', bytes.fromhex(p['payload_hex'])) for p in parser(programs[name])]
        assert records == expected
        matched += len(records)
        assert stage['same_dbv_replay']['observed_writes'] == [
            {'length': 3, 'type': 57, 'mode': 'hs', 'payload': '51 0e 10'}]
        start = datetime.fromisoformat(stage['hold_start_utc'])
        finish = datetime.fromisoformat(stage['hold_end_utc'])
        assert 7 <= (finish-start).total_seconds() < 8
        center = ((start-origin).total_seconds() + (finish-origin).total_seconds())/2
        mask = (pts >= center-1.25) & (pts < center+1.25)
        assert mask.sum() >= 70
        selected = profiles[mask]
        # Spatial detrend only: retain stationary as well as moving stripes.
        spectrum = analyze_profiles(selected, peak_count=8)
        spectrum_file = OUT / (label + '-spectrum-spatial-v2.npz')
        np.savez_compressed(spectrum_file, **{
            key: spectrum[key] for key in (
                'frequencies_cycles_per_row', 'total_power', 'coherent_power',
                'incoherent_power', 'raw_mean_per_frame')})
        frequencies = spectrum['frequencies_cycles_per_row']
        amplitudes = spectrum['total_rms_amplitude']
        peak = int(amplitudes.argmax())
        old_component = analyze_profiles(selected, frequencies=[1/93.43], peak_count=0)
        q = float(old_component['total_rms_amplitude'][0])
        mean = float(selected.mean()-16)
        result = {'label': label, 'window_s': [center-1.25, center+1.25],
                  'frames': int(mask.sum()), 'dominant_period_px': float(1/frequencies[peak])
                  if 0 < peak < len(frequencies)-1 else None,
                  'spectral_search_boundary': peak in (0, len(frequencies)-1),
                  'q93_total_rms_Y_codes': q,
                  'q93_coherent_Y_codes': float(old_component['coherent_amplitude'][0]),
                  'q93_incoherent_rms_Y_codes': float(old_component['incoherent_rms_amplitude'][0]),
                  'spatial_spectrum_peaks': spectrum['peaks'],
                  'full_spectrum_npz': str(spectrum_file.relative_to(ROOT)),
                  'raw_mean_Y': spectrum['raw_mean'],
                  'power_partition_max_abs_error': spectrum['power_partition_max_abs_error'],
                  'mean_Y_minus16': mean, 'normalized_q': q/mean,
                  'pixel_Y_min': int(pixels[mask].min()), 'pixel_Y_max': int(pixels[mask].max()),
                  'fraction_Y_ge235': float(np.mean(pixels[mask] >= 235))}
        results.append(result)
        image_data = subprocess.check_output([
            'ffmpeg', '-v', 'error', '-ss', str(center), '-i', str(video),
            '-frames:v', '1', '-vf', 'eq=gamma=2,scale=640:360',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
        image = Image.frombytes('RGB', (640, 360), image_data)
        col, row = index % 3, index // 3
        sheet.paste(image, (col*640, row*396+36))
        draw.text((col*640+8, row*396+8), f'{label} | {center:.2f}s', font=font, fill='white')

    for index in (1, 3, 5, 7):
        left, current, right = results[index-1:index+2]
        current['normalized_q_ratio_to_adjacent_stock'] = current['normalized_q'] / ((left['normalized_q']+right['normalized_q'])/2)
        current['mean_signal_ratio_to_adjacent_stock'] = current['mean_Y_minus16'] / ((left['mean_Y_minus16']+right['mean_Y_minus16'])/2)
    trace = (PRIVATE / 'trace-final.txt').read_text()
    assert 'LOST' not in trace
    entries = [tuple(map(int, row)) for row in re.findall(r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)', trace)]
    assert entries == [(0,253,64),(253,247,64),(500,254,64),(754,110,64),(864,11,0)]*9
    returns = [int(v) for v in re.findall(r'\bmode_return:.*?rc=(-?\d+)', trace)]
    controller = [int(v) for v in re.findall(r'\bmode_ctrl_return:.*?rc=(-?\d+)', trace)]
    assert returns == [0]*45 and controller and min(controller) >= 0
    profile = (PRIVATE / 'probe-profile.txt').read_text()
    for name in ('mode_entry', 'mode_return', 'mode_ctrl_return'):
        rows = re.findall(r'^\s*'+name+r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
        assert len(rows) == 1 and int(rows[0][1]) == 0
    comparison = ROOT / 'artifacts/optical/pacman_dsi_blocks_redraw_comparison_spatial_v2.png'
    sheet.save(comparison)
    output = {'capture': str((OUT/'run.json').relative_to(ROOT)), 'video': report['video'],
              'video_bytes': video.stat().st_size, 'decoded_frames': len(pts),
              'roi_xywh': [540,190,60,500], 'stages': results,
              'method': 'Spatial v2: original limited-range Y; per-frame quadratic spatial detrend only; full spatial spectrum through Nyquist; separate total/coherent/incoherent powers. Static image content also contributes. q93 is an image component, not Hz/depth. Comparison images alone use equal gamma2.',
              'window_alignment': 'Coarse native record-tap origin, central2.5s windows inside7s holds; contact-sheet inspection required. No sensor-to-video timestamp accuracy claim.',
              'native': {'table_packets_matched': matched, 'post_table_DBV_writes': 9,
                         'callback_returns': returns, 'controller_return_count': len(controller),
                         'controller_negative_returns': 0, 'probe_misses': 0},
              'pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False,
              'target_restored': report['target_restored'],
              'camera_original_restoration_pending': True,
              'comparison_image': str(comparison.relative_to(ROOT)),
              'limits': ['Image amplitude is not calibrated modulation depth/luminance.',
                         'Same DBV does not guarantee same optical brightness across programs.',
                         'No independently measured panel temperature or numerical carrier frequency.']}
    (OUT/'analysis_spatial_v2.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({'stages': results, 'native': output['native']}, indent=2))


if __name__ == '__main__':
    main()
