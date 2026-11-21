#!/usr/bin/env python3
"""R46 fallback only if ordinary settings cannot alternate hardware modes with R45 bright at 120 fps.

Usage: python3 common.py R45/bright.mp4 R46 > common.json
Writes R46/media-build/common24.mp4 after offline verification.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path


FPS, SECONDS = 24, 2400
COUNT = FPS * SECONDS
R45 = Path(__file__).resolve().parents[1] / 'direct_camera_r45_20261121/stimulus.json'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def ffmpeg(*args):
    return subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', *args])


def probe(path, *args):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', *args, '-of', 'json', path]))


def header_fields(path):
    trace = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', path, '-frames:v', '1',
                            '-c', 'copy', '-bsf:v', 'trace_headers', '-f', 'null', '-'],
                           check=True, capture_output=True, text=True).stderr
    return re.findall(r'\[trace_headers @ [^\]]+\]\s+\d+\s+(\S+)\s+[01]+ = (-?\d+)', trace)


def verify_headers(ref, clip):
    # hevc_metadata also adds an explicit VPS clock. Check both in-band and MP4 headers.
    vps = dict(vps_timing_info_present_flag='1', vps_num_units_in_tick='1', vps_time_scale='24',
               vps_poc_proportional_to_timing_flag='0', vps_num_hrd_parameters='0')
    clocks = []
    for path, timing in ((ref, {'vps_timing_info_present_flag': '0', 'vui_time_scale': '120'}),
                         (clip, {**vps, 'vui_time_scale': '24'})):
        fields = header_fields(path)
        for key, value in timing.items():
            check([v for k, v in fields if k == key] == [value, value], f'{path.name}: {key}')
        clocks.append([(k, v) for k, v in fields if k not in timing and k != 'rbsp_alignment_zero_bit'])
    check(clocks[0] == clocks[1], 'non-clock HEVC header change')


def unchanged_units(path):
    # VPS/SPS carry the clock; every other NAL, including coded slices and HDR SEI, must match.
    return ffmpeg('-i', path, '-frames:v', str(FPS), '-c:v', 'copy', '-bsf:v',
                  'hevc_mp4toannexb,filter_units=remove_types=32|33', '-f', 'hevc', 'pipe:1')


def sample(path, index, stream, expected_sei, raw):
    sec, offset = divmod(index, FPS)
    rows = probe(path, '-read_intervals', f'{sec}%+#{offset+1}', '-show_frames',
                 '-show_entries', 'frame=pts,pts_time,side_data_list')['frames']
    row = rows[-1]
    check(len(rows) == offset + 1 and row['pts'] * Fraction(stream['time_base']) == Fraction(index, FPS),
          f'frame {index}: presentation timestamp')
    side = {v['side_data_type']: {k: n for k, n in v.items() if k != 'side_data_type'}
            for v in row['side_data_list']}
    check(all(side.get(k) == v for k, v in expected_sei.items()), f'frame {index}: HDR10 SEI')
    raster = ffmpeg('-ss', str(sec), '-i', path, '-vf', f'select=eq(n\\,{offset})', '-frames:v', '1',
                    '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p10le', '-f', 'rawvideo', 'pipe:1')
    check(raster == raw, f'frame {index}: nonuniform or wrong code')
    return dict(frame_index=index, pts=row['pts'], pts_time_s=row['pts_time'],
                full_plane_codes=dict(Y=940, Cb=512, Cr=512))


def verify_copies(clip, stream, raw):
    hashes = ffmpeg('-i', clip, '-frames:v', str(FPS), '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p10le',
                    '-f', 'framehash', '-hash', 'sha256', 'pipe:1').decode().splitlines()
    check([s.split(',')[-1].strip() for s in hashes if s and not s.startswith('#')] ==
          [hashlib.sha256(raw).hexdigest()] * FPS, 'nonuniform first GOP')
    rows = probe(clip, '-show_packets', '-show_data_hash', 'sha256', '-show_entries',
                 'packet=pts,dts,duration,flags,data_hash')['packets']
    check(len(rows) == COUNT, 'packet count')
    step = 1 / (FPS * Fraction(stream['time_base']))
    for i, row in enumerate(rows):
        j = i % FPS
        check(row['pts'] == row['dts'] == i * step and row['duration'] == step and
              ('K' in row['flags']) == (j == 0) and row['data_hash'] == rows[j]['data_hash'],
              f'packet {i}: cadence or repeated GOP mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('r46', type=Path)
    args = parser.parse_args()
    ref = args.reference
    receipt = json.loads(R45.read_text())
    source, = probe(ref, '-show_streams')['streams']
    check({k: source.get(k) for k in receipt['stream']} == receipt['stream'], 'R45 reference stream')
    n = source['width'] * source['height']
    raw = (940).to_bytes(2, 'little') * n + (512).to_bytes(2, 'little') * (n // 2)
    hdr = receipt['hdr10_sei_matching_reference']

    os.umask(0o077)
    build = args.r46 / 'media-build'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build) as tmp:
        gop, clip = (Path(tmp) / s for s in ('second.mp4', 'common24.mp4'))
        mux = ('-video_track_timescale', '15360', '-tag:v', 'hvc1', '-movflags', '+faststart+write_colr')
        ffmpeg('-i', ref, '-map', '0:v:0', '-frames:v', '24', '-c:v', 'copy', '-bsf:v',
               'hevc_metadata=tick_rate=24/1,setts=pts=PTS*5:dts=DTS*5:duration=DURATION*5', *mux, gop)
        ffmpeg('-stream_loop', str(SECONDS-1), '-i', gop, '-map', '0:v:0', '-c:v', 'copy', *mux, clip)
        stream, = probe(clip, '-show_streams')['streams']
        expected = dict(source, r_frame_rate='24/1', avg_frame_rate='24/1', nb_frames=str(COUNT))
        check(all(stream.get(k) == expected.get(k) for k in (stream.keys() | expected.keys()) -
                  {'bit_rate', 'extradata_size'}), 'unexpected stream metadata change')
        verify_headers(ref, clip)
        check(unchanged_units(ref) == unchanged_units(clip), 'R45 slice/SEI byte mismatch')
        samples = [sample(clip, i, stream, hdr, raw) for i in (0, COUNT // 2, COUNT - 1)]
        verify_copies(clip, stream, raw)
        result = dict(file='media-build/common24.mp4', bytes=clip.stat().st_size,
                      use_only_if='Ordinary settings cannot alternate hardware modes with R45 bright at 120 fps.',
                      refresh_multipliers={'120_Hz': 5, '144_Hz': 6}, reference='R45/bright.mp4',
                      ffmpeg_version=subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
                      stream={k: stream[k] for k in receipt['stream']},
                      hevc_clocks=dict(vui_tick_rate='24/1', vps_tick_rate='24/1'),
                      hdr10_sei_matching_reference=hdr, decoded_full_raster_samples=samples,
                      verification='First 24 coded pictures and SEI byte-identical to R45. All 24 decoded '
                                   'to the constant field. All 2400 GOP copies matched by packet SHA-256; '
                                   '57600 packets at PTS=DTS=n/24 s, each lasting 1/24 s.')
        clip.replace(build / clip.name)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
