#!/usr/bin/env python3
"""Offline owner-reference check; image-space observations, never measured PWM Hz."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from optical_spectrum import analyze_profiles


def summarize(profiles, minimum, maximum):
    result = analyze_profiles(profiles, frequency_min=minimum,
                              frequency_max=maximum, peak_count=4)
    np.testing.assert_allclose(result['total_power'],
                               result['coherent_power'] + result['incoherent_power'],
                               rtol=1e-12, atol=1e-12)
    return {key: result[key] for key in ('frames', 'rows', 'raw_mean', 'peaks',
                                        'nominal_record_bin_width_cycles_per_row')}


def phase_gradient(pixels, x0, y0, qy):
    """Fit one frame's band phase across columns; no temporal subtraction."""
    height, width = pixels.shape
    assert width % 4 == 0
    strips = pixels.reshape(height, width//4, 4).mean(axis=2)
    y = np.arange(y0, y0+height)
    x = np.arange(x0, x0+width, 4) + 1.5
    design = np.column_stack((np.polynomial.legendre.legvander(
        np.linspace(-1, 1, height), 2), np.cos(2*np.pi*qy*y), np.sin(2*np.pi*qy*y)))
    weights = np.sqrt(np.hanning(height))
    coefficients = np.linalg.lstsq(design*weights[:, None],
                                    strips*weights[:, None], rcond=None)[0]
    phase = np.unwrap(np.angle(coefficients[-2] - 1j*coefficients[-1]))/(2*np.pi)
    slope, intercept = np.polyfit(x, phase, 1)
    return {'qx_cycles_per_pixel': float(slope), 'qy_cycles_per_pixel': qy,
            'stripe_dy_dx': float(-slope/qy),
            'phase_residual_rms_cycles': float(np.std(phase-(slope*x+intercept)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('photo', type=Path)
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Do not overwrite previous evidence')
    with Image.open(args.photo) as image:
        assert image.size == (4096, 3072) and image.getexif().get(274) == 1
        exif = image.getexif().get_ifd(34665)
        exposure = float(exif[33434])
        iso = int(exif[34855])
        gray = np.asarray(image, dtype=np.float64) @ np.array([.2126, .7152, .0722])
    # Narrow columns avoid smearing the visibly slanted fine bands. No temporal
    # average is subtracted, including from the single stationary photograph.
    photos = []
    for x in (400, 900, 1800, 2100, 3000, 3600):
        profile = gray[850:2350, x-16:x+16].mean(axis=1)
        photos.append({'roi_xywh': [x-16, 850, 32, 1500],
                       **summarize(profile[None, :], 1/250, 1/12)})
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams',
        '-show_frames', '-show_entries',
        'stream=width,height,nb_frames,avg_frame_rate,duration:frame=best_effort_timestamp_time',
        '-of', 'json', str(args.video)], text=True))
    stream = probe['streams'][0]
    assert (stream['width'], stream['height']) == (1280, 720)
    pts = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    assert len(pts) == 165 and np.all(np.diff(pts) > 0)
    pts -= pts[0]
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-noautorotate', '-i', str(args.video), '-vf',
        'crop=1000:360:160:220:exact=1,extractplanes=y', '-fps_mode', 'passthrough',
        '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 360, 1000)
    assert len(pixels) == len(pts) == int(stream['nb_frames'])
    videos = []
    for x in (240, 440, 680, 840, 1040):
        for start, stop in ((30, 135), (30, 65), (65, 100), (100, 135)):
            profiles = pixels[start:stop, :, x-164:x-156].mean(axis=2)
            videos.append({'roi_xywh': [x-4, 220, 8, 360],
                           'frame_interval': [start, stop],
                           'pts_interval_s': [float(pts[start]), float(pts[stop-1])],
                           **summarize(profiles, 1/80, 1/6)})
    photo_periods = [p['peaks'][0]['period_rows'] for p in photos]
    video_periods = [v['peaks'][0]['period_rows'] for v in videos
                     if v['frame_interval'] == [30, 135]]
    scale = 4096/1280
    # Ranges are ROI/window sensitivity, NOT confidence intervals or matched
    # scene coordinates. Pixel scale agreement does not supply a timebase.
    ratio = float(np.median(photo_periods)/np.median(video_periods))
    row_times = [1/(2160*p) for p in photo_periods]
    directions = []
    qy = 1/float(np.median(video_periods))
    for frame in (30, 65, 100, 134):
        directions.append({'frame': frame, 'roi_xywh': [700, 260, 400, 250],
                           **phase_gradient(pixels[frame, 40:290, 540:940], 700, 260, qy)})
    result = {
        'scope': 'existing owner photo/video of reported2160Hz Nothing; offline only',
        'inputs': {'photo': str(args.photo), 'video': str(args.video)},
        'photo_exif': {'size': [4096, 3072], 'orientation': 1,
                       'exposure_seconds': exposure, 'iso': iso},
        'video': {'stream': stream, 'decoded_frames': len(pts),
                  'pts_step_median_s': float(np.median(np.diff(pts)))},
        'photo_profiles': photos, 'video_profiles': videos,
        'video_fine_band_directions': directions,
        'spatial_scale_check': {
            'photo_period_range_px': [min(photo_periods), max(photo_periods)],
            'video_period_range_px': [min(video_periods), max(video_periods)],
            'median_period_ratio': ratio, 'width_scale': scale,
            'ratio_over_width_scale': ratio/scale,
            'matched_scene_coordinates': False},
        'conditional_timebase_not_a_measurement': {
            'assumed_reference_component_hz': 2160,
            'assumptions': ['visible component is owner-reported2160Hz, not another harmonic',
                            'sensor time axis maps to output y',
                            'panel row tangent approximated by output y',
                            '3072 output rows represent the full active-array height (unverified)',
                            'no ISP spatial warp or cross-row phase contribution'],
            'photo_seconds_per_row_range': [min(row_times), max(row_times)],
            'photo_3072_row_span_seconds_range': [min(row_times)*3072, max(row_times)*3072],
            'separate_preview_hal_skew_seconds': .027011343,
            'skew_captured_during_this_photo': False},
        'interpretation': ['fine spatial train is reproducible across columns and video subwindows',
                           'photo/video amplitudes are different encoded domains; do not compare them',
                           'no optical fundamentalHz, comfort or low-envelope absence established',
                           'Nothing reference does not calibrate the other Nothing-camera sensor'],
        'new_dsi_or_recording_actions': False,
        'lenovo_pwm_hz': 'unknown', 'greater_equal_2000_hz_verified': False}
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result['spatial_scale_check'], indent=2))
    print(json.dumps(result['conditional_timebase_not_a_measurement'], indent=2))


if __name__ == '__main__':
    main()
