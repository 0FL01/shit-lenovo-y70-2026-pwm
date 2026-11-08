#!/usr/bin/env python3
"""Offline detectability of a camera-row period; no device I/O or physical Hz.
Usage: .venv/bin/python artifacts/qualification_dbv828_20261108/analyze.py PRIVATE_DIR --output NEW.json
DBV828 is the coordinator's capture attribution, not embedded video metadata.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from camera_capture_metadata import validate_capture
from optical_spectrum import analyze_profiles

ROIS = {'left': [220,70,40,540], 'main': [260,70,40,540],
        'right': [320,70,40,540], 'offscreen': [900,70,40,540]}
WINDOWS = [(30,255), (30,105), (105,180), (180,255)]


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_dir', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    check(not args.output.exists(), 'Refusing to overwrite output')
    video = args.private_dir/'qualification_clip.mp4'
    check(video.is_file(), 'Saved video absent')
    first = validate_capture((args.private_dir/'current_camera_recording1.txt').read_text(), require_recording=True)
    last = validate_capture((args.private_dir/'current_camera_recording2.txt').read_text(), first, require_recording=True)
    profile_keys = ('exposure_ns','iso','focus_diopters','crop','zoom','eis_mode','ois_mode',
                    'frame_duration_ns','rolling_shutter_skew_ns')
    probe = json.loads(subprocess.check_output([
        'ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'stream=codec_name,width,height,pix_fmt,color_range,duration,nb_frames:frame=best_effort_timestamp_time',
        '-of','json',str(video)], text=True))
    stream = probe['streams'][0]
    check((stream['width'],stream['height'],stream['pix_fmt'],stream['color_range']) ==
          (1280,720,'yuv420p','tv'), 'Unexpected saved video format')
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    check(len(pts)==int(stream['nb_frames'])==292 and np.all(np.diff(pts)>0), 'Bad frame timing/count')
    raw = subprocess.check_output([
        'ffmpeg','-v','error','-noautorotate','-i',str(video),'-vf',
        'crop=720:540:220:70,extractplanes=y','-fps_mode','passthrough',
        '-enc_time_base','demux','-f','rawvideo','-pix_fmt','gray','-'])
    check(len(raw)==292*540*720, 'Wrong decoded byte count')
    frames = np.frombuffer(raw,dtype=np.uint8).reshape(292,540,720)
    prior = json.loads((ROOT/'artifacts/a9_c1_a001_20261108_06/optical_analysis_v2.json').read_text())
    reference_q = 1/prior['fixed_stock_fine_period_rows']
    records = []
    for roi,(x,y,width,height) in ROIS.items():
        pixels = frames[:,:,x-220:x-220+width]
        profiles = pixels.mean(axis=2)
        for start,end in WINDOWS:
            p = profiles[start:end]
            spectrum = analyze_profiles(p,n_fft=8192,frequency_min=0,frequency_max=.5,peak_count=12)
            fixed = analyze_profiles(p,frequencies=[reference_q,2*reference_q,3*reference_q])
            check(spectrum['power_partition_max_abs_error']<1e-10,'Invalid power partition')
            records.append({'roi':roi,'frames':[start,end],'pts_seconds':[float(pts[start]),float(pts[end-1])],
                            'mean_y':float(p.mean()),'min_y':int(pixels[start:end].min()),
                            'max_y':int(pixels[start:end].max()),'peaks_full_nyquist':spectrum['peaks'],
                            'fixed_total_rms_y':fixed['total_rms_amplitude'].tolist(),
                            'fixed_coherent_y':fixed['coherent_amplitude'].tolist(),
                            'fixed_incoherent_rms_y':fixed['incoherent_rms_amplitude'].tolist()})
    main_record = next(r for r in records if r['roi']=='main' and r['frames']==[30,255])
    background = next(r for r in records if r['roi']=='offscreen' and r['frames']==[30,255])
    result = {'source_video':'Private saved camera qualification clip','source_bytes':video.stat().st_size,
              'stream':stream,'settings_provenance':'Two saved during-recording camera-service snapshots; active request/result and advancing recording stream validated.',
              'camera_profile':{k:first['result'][k] for k in profile_keys},
              'snapshot_advance_frames':last['frame_count']-first['frame_count'],
              'snapshot_advance_seconds':(last['timestamp_ns']-first['timestamp_ns'])/1e9,
              'target_dbv_attribution':828,
              'target_dbv_provenance':'Coordinator contemporaneous attribution; no synchronized target DBV/C1 log embedded in this clip.',
              'rois_xywh':ROIS,'records':records,
              'reference_stock3600':'artifacts/a9_c1_a001_20261108_06/optical_analysis_v2.json',
              'reference_stock3600_period_rows':1/reference_q,
              'free_main_peak_period_rows':main_record['peaks_full_nyquist'][0]['period_rows'],
              'main_to_offscreen_fixed_q_amplitude_ratio':main_record['fixed_total_rms_y'][0]/background['fixed_total_rms_y'][0],
              'signal_interpretation':'Reproducible screen-localized camera image component. Off-screen comparison is not a calibrated sensor or optical SNR.',
              'normalization':'Raw Y-code amplitudes only; no division by mean(Y)-16 near the dark floor.',
              'nominal_frequency_resolution_cycles_per_row':1/540,
              'zero_padded_grid_step_cycles_per_row':1/8192,'physical_pwm_hz':None,
              'limits':['Separate captures and separately obtained C1 values are not simultaneous causal measurements.',
                        'Black floor/ISP/codec can distort amplitude and pulse shape; no modulation-depth claim.',
                        'A common image period can be a harmonic, envelope or scan alias, not physical fundamental PWM.',
                        'Equal FFT bins are not a confidence interval or exact equality of physical frequencies.']}
    with args.output.open('x') as handle:
        json.dump(result,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps({k:result[k] for k in ['free_main_peak_period_rows','reference_stock3600_period_rows',
                                          'main_to_offscreen_fixed_q_amplitude_ratio','physical_pwm_hz']}))


if __name__=='__main__':
    main()
