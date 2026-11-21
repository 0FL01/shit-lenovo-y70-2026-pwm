#!/usr/bin/env python3
"""Build bright.mp4 from the R44 day field and write the verified receipt to stdout.

Usage: python3 stimulus.py R44/hdr120-2400.mp4 R45 > stimulus.json
"""

import argparse
import json
import os
import re
import runpy
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path


R43 = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'direct_camera_r43_20261121/clips.py'))
W, H, MASTER, ffmpeg = (R43[k] for k in ('W', 'H', 'MASTER', 'ffmpeg'))
FPS, SECONDS, Y = 120, 2400, 940
HDR = ('Mastering display metadata', 'Content light level metadata')
STREAM = dict(codec_type='video', codec_name='hevc', profile='Main 10', codec_tag_string='hvc1',
              width=W, height=H, pix_fmt='yuv420p10le', color_range='tv', color_space='bt2020nc',
              color_transfer='smpte2084', color_primaries='bt2020', r_frame_rate='120/1',
              avg_frame_rate='120/1', start_pts=0, nb_frames=str(FPS * SECONDS))


def check(ok, why):
    if not ok:
        raise ValueError(why)


def probe(path, *args):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', *args, '-of', 'json', path]))


def stream_info(path):
    s, = probe(path, '-show_streams')['streams']
    for k, v in STREAM.items():
        check(s.get(k) == v, f'{path.name}: {k}: {s.get(k)!r}, expected {v!r}')
    check(Fraction(s['duration_ts']) * Fraction(s['time_base']) == SECONDS, 'track duration')
    return {k: s[k] for k in (*STREAM, 'level', 'duration', 'duration_ts', 'time_base')}


def vui(path):
    trace = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', path, '-map', '0:v:0',
                            '-frames:v', '1', '-c:v', 'copy', '-bsf:v', 'trace_headers',
                            '-f', 'null', '-'], check=True, capture_output=True, text=True).stderr
    values = {}
    for k, v in re.findall(r'\[trace_headers @ [^\]]+\]\s+\d+\s+(\w+)\s+[01]+ = (\d+)', trace):
        if k == 'sps_extension_present_flag' and values:
            break
        if values or k == 'vui_parameters_present_flag':
            values[k] = int(v)
    check([values[k] for k in ('vui_parameters_present_flag', 'video_full_range_flag', 'colour_primaries',
                               'transfer_characteristics', 'matrix_coefficients', 'vui_num_units_in_tick',
                               'vui_time_scale')] == [1, 0, 9, 16, 9, 1, FPS], 'HEVC VUI')
    return values


def sample(path, stream, index, luma):
    # Seek to the closed-GOP boundary then decode through the requested frame.
    sec, offset = divmod(index, FPS)
    frames = probe(path, '-read_intervals', f'{sec}%+#{offset+1}', '-show_frames',
                   '-show_entries', 'frame=pts,pts_time,side_data_list')['frames']
    f = frames[-1]
    check(len(frames) == offset + 1 and Fraction(stream['time_base']) * f['pts'] == Fraction(index, FPS),
          f'{path.name}: wrong presentation timestamp for frame {index}')
    side = {s['side_data_type']: s for s in f['side_data_list']}
    sei = {k: {a: b for a, b in side[k].items() if a != 'side_data_type'} for k in HDR}
    raster = ffmpeg('-ss', str(sec), '-i', path, '-map', '0:v:0', '-vf', f'select=eq(n\\,{offset})',
                    '-frames:v', '1', '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p10le',
                    '-f', 'rawvideo', 'pipe:1')
    n = W * H
    planes = (raster[:2*n], raster[2*n:5*n//2], raster[5*n//2:])
    codes = {}
    for plane, name, code, count in zip(planes, ('Y', 'Cb', 'Cr'), (luma, 512, 512), (n, n//4, n//4)):
        check(plane == code.to_bytes(2, 'little') * count, f'{path.name}: frame {index}, plane {name}')
        codes[name] = int.from_bytes(plane[:2], 'little')
    return dict(frame_index=index, pts=f['pts'], pts_time_s=f['pts_time'], full_plane_codes=codes), sei


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('r44day', type=Path)
    parser.add_argument('r45', type=Path)
    args = parser.parse_args()
    ref = args.r44day
    ref_stream, ref_vui = stream_info(ref), vui(ref)
    ref_sample, ref_sei = sample(ref, ref_stream, 0, 573)
    cll = ref_sei[HDR[1]]
    check((cll['max_content'], cll['max_average']) == (204, 204), 'unexpected R44 day CLL')

    os.umask(0o077)
    build = args.r45 / 'media-build'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build) as d:
        field, gop, bright = (Path(d) / n for n in ('field.yuv', 'second.mp4', 'bright.mp4'))
        # R43 Main 10 closed-GOP recipe; preserve the R44 day CLL instead of recalculating it.
        params = ('pools=none:frame-threads=1:log-level=error:bframes=0:open-gop=0:'
                  f'keyint={FPS}:scenecut=0:range=limited:colorprim=bt2020:transfer=smpte2084:'
                  f'colormatrix=bt2020nc:hdr10=1:master-display={MASTER}:'
                  f'max-cll={cll["max_content"]},{cll["max_average"]}')
        # Use R43's rawvideo input: direct transcoding signals an extra chroma location in the VUI.
        ffmpeg('-i', ref, '-map', '0:v:0', '-vf', f'lutyuv=y={Y}', '-frames:v', '1',
               '-pix_fmt', 'yuv420p10le', '-f', 'rawvideo', field)
        ffmpeg('-stream_loop', '-1', '-f', 'rawvideo', '-pixel_format', 'yuv420p10le',
               '-video_size', f'{W}x{H}', '-framerate', str(FPS), '-i', field, '-frames:v', str(FPS),
               '-c:v', 'libx265', '-profile:v', 'main10', '-preset', 'ultrafast', '-qp', '8',
               '-x265-params', params, '-color_range', 'tv', '-colorspace', 'bt2020nc',
               '-color_trc', 'smpte2084', '-color_primaries', 'bt2020', '-tag:v', 'hvc1', gop)
        ffmpeg('-stream_loop', str(SECONDS-1), '-i', gop, '-map', '0:v:0', '-c', 'copy',
               '-tag:v', 'hvc1', '-movflags', '+faststart+write_colr', bright)

        stream, bits = stream_info(bright), vui(bright)
        for name, got, want in (('stream', stream, ref_stream), ('VUI', bits, ref_vui)):
            diff = {k: (got.get(k), want.get(k)) for k in got.keys() | want.keys() if got.get(k) != want.get(k)}
            check(not diff, f'{name} mismatch (R45, R44 day): {diff}')
        samples = []
        for index in (0, FPS * SECONDS // 2, FPS * SECONDS - 1):
            row, sei = sample(bright, stream, index, Y)
            check(sei == ref_sei, f'R45 frame {index}: HDR10 SEI differs from R44 day')
            samples.append(row)
        receipt = dict(file=bright.name, bytes=bright.stat().st_size,
                       reference=dict(id='r44day', file=ref.name, sample=ref_sample),
                       ffmpeg_version=subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
                       nominal_st2084_cd_m2=R43['pq_nits'](Y), stream=stream,
                       hevc_vui_matching_reference=bits, hdr10_sei_matching_reference=sei,
                       decoded_full_raster_samples=samples)
        bright.replace(args.r45 / bright.name)
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
