#!/usr/bin/env python3
"""Bind R43 optical windows to original DNGs, frames.csv and target snapshots.

python windows.py ARCHIVE frames.csv [--log run.log] > windows.csv
The default log accounts for the full archive window inventory. An explicit log
may select a subset; pass the matching frames.csv. A snapshot is boundary
evidence, not continuous telemetry, a panel-register readback, or photometry.
"""

import argparse
import csv
from hashlib import blake2b
from math import isfinite
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r42_20261121.measure import decode_dng_bytes, extract_metadata
from direct_camera_r43_20261121.measure import ROI, phase_info
from direct_camera_r43_20261121 import state


PHASE = r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*'
POS = r'[1-9][0-9]*'
FIELDS = (rf'({PHASE}) scene=(sdr|hdr) BL=({POS}) hwc=(0|{POS}) '
          rf'hz=({POS}) ns=({POS}) wake=({POS})')
PRE = re.compile('PRE ' + FIELDS)
POST = re.compile('POST ' + FIELDS + rf' count=({POS})')
FRAME = re.compile(rf'frame ({PHASE})__({POS}) ({POS})')
SUFFIXES = ('sf', 'display', 'thermal', 'bl', 'session', 'top')
PLAYER = 'com.alphainventor.filemanager'
CLASS = 'viewer.VideoPlayerActivity'
COMPONENT = rf'{re.escape(PLAYER)}/(?:{re.escape(PLAYER)})?\.{re.escape(CLASS)}'
SURFACE = rf'[0-9a-f]+ SurfaceView\[{COMPONENT}\]\(BLAST\)#[0-9]+'
CONSUMER = '(BLAST Consumer)pid:'
LAYER = re.compile(r'^layer: \d+ name:[ \t]*(.*?) z: (-?\d+) composition: (\d+/\d+) '
                   r'alpha: (\d+) format:[ \t]*(\S+) dataspace:(0x[0-9a-fA-F]+) '
                   r'transform: (\S+) buffer_id: (0x[0-9a-fA-F]+) secure: \d+[ \t]*$', re.M)
SDM = {'sdr': (0x10810000, 1, 'BT709'), 'hdr': (0x11c60000, 16, 'PQ')}
FRAME_FIELDS = ('phase group scene frame_n exposure_us iso width height orientation '
                'focal_mm cfa y0 y1 x0 x1 black_dn white_dn').split()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def original(path):
    require(not path.is_symlink() and path.is_file(), f'{path.name}: missing or not an original file')
    return path


def read_windows(log):
    pre = None
    phases = set()
    for number, line in enumerate(original(log).read_text().splitlines(), 1):
        kind = line.split(maxsplit=1)[:1]
        context = f'{log.name}:{number}'
        if kind == ['PRE']:
            m = PRE.fullmatch(line)
            require(m and pre is None and m[1] not in phases, f'{context}: invalid, nested or repeated PRE')
            pre, sizes = m.groups(), []
        elif kind == ['frame']:
            m = FRAME.fullmatch(line)
            require(pre and m and m[1] == pre[0] and int(m[2]) == len(sizes) + 1,
                    f'{context}: malformed, unbound or out-of-order frame')
            sizes.append(int(m[3]))
        elif kind == ['POST']:
            m = POST.fullmatch(line)
            require(pre and sizes and m and m.groups()[:-1] == pre and int(m[8]) == len(sizes),
                    f'{context}: mismatched POST state or count')
            phase, scene, *numbers = pre
            phases.add(phase)
            yield phase, scene, *map(int, numbers), sizes
            pre = None
        # Non-receipt diagnostic lines do not contribute evidence.
    require(phases and pre is None, f'{log.name}: empty log or unclosed window')


def video_evidence(sf, sdm, ident, scene):
    ds, tr, eotf = SDM[scene]
    # The current SDM3 layer list precedes the Color Modes section. An allocation
    # or a supported dataspace below that section cannot substantiate a layer.
    active_list, separator, _ = sdm.partition('----------Color Modes---------')
    require(separator, 'missing SDM current layer list boundary')
    candidates = [line for line in active_list.splitlines()
                  if line.startswith('layer:') and f'SurfaceView[{PLAYER}/' in line]
    require(len(candidates) == 1 and (layer := LAYER.fullmatch(candidates[0])),
            'missing, malformed or ambiguous current SDM video layer')
    name, z, composition, alpha, fmt, dataspace, transform, buffer = layer.groups()
    prefix = re.match(SURFACE, name)
    require(prefix and (CONSUMER.startswith(name[prefix.end():]) or
                        re.fullmatch(re.escape(CONSUMER) + r'[0-9]+', name[prefix.end():]))
            and composition == '2/2' and alpha == '65535' and fmt.startswith(('Y_CBCR_', 'Y_CRCB_'))
            and int(dataspace, 16) == ds and transform == '0/0/0' and int(buffer, 16) != 0,
            'wrong SDM video dataspace, opacity, composition, format or buffer')

    physical = state.physical(sf, ident)
    require(re.search(r'^ +isEnabled=true\b', physical, re.M), 'physical output not enabled')
    parts = re.split(r'^ *- Output Layer 0x[0-9a-f]+\(([^\n]*)\)[ \t]*$', physical, flags=re.M)
    outputs = [body for label, body in zip(parts[1::2], parts[2::2]) if label == prefix[0]]
    require(len(outputs) == 1 and re.search(
        r'^ +Region visibleNonTransparentRegion \([^\n]*count=1\)\n'
        r'^ +\[\s*0,\s*0,\s*1440,\s*3168\s*\][ \t]*$', outputs[0], re.M),
        'SDM video layer does not cover the calibrated SF output')
    output = outputs[0]
    current = re.search(r'^ *forceClientComposition=false[^\n]*? displayFrame=\[([^\]]+)\] '
                        r'sourceCrop=\[([^\]]+)\] bufferTransform=0 \(0\) '
                        r'dataspace=[^\n]*? \((\d+)\) whitePointNits=', output, re.M)
    require(current and int(current[3]) == ds and
            re.search(r'^ +hwc: layer=0x[0-9a-f]+ composition=DEVICE \(2\)', output, re.M),
            'SF current video frame not in matching DEVICE composition/dataspace')
    dst = tuple(map(int, current[1].split()))
    src = tuple(map(float, current[2].split()))
    require(dst == (0, 0, 1440, 3168) and src == (0, 0, 720, 1584),
            'video destination or source crop differs from the full-field calibration geometry')

    # SDM reports transfer numerically (Tr) per current DPU pipe, not in its
    # support table. This is the programmed video transfer, not panel EOTF.
    dpu = state.block(sdm, r'^ *Table for DPU - 0[ \t]*\n', r'^------------Active Fences Info')
    transfers = []
    for line in dpu.splitlines():
        if line.startswith('|'):
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) == 14 and cells[5] == fmt and cells[8] == z:
                transfers.append(cells[-1])
    require(transfers and all(t == str(tr) for t in transfers), 'wrong or missing current SDM video Tr')
    return dict(video_dataspace=f'0x{ds:08x}', sdm_tr=tr, sdm_eotf=eotf,
                video_source_ltrb=' '.join(format(v, 'g') for v in src),
                video_display_ltrb=' '.join(map(str, dst)))


def snapshot(archive, stem, scene, bl, hwc, hz, wake):
    sf, display, thermal, raw_bl, session, top = (
        original(archive / f'{stem}.{suffix}').read_text() for suffix in SUFFIXES)
    try:
        require(raw_bl.strip() == str(bl), 'BL differs from archive receipt')
        require(session.strip() == f'running\nactive: verified wake={wake}', 'session missing or different wake')
        require(re.fullmatch(rf'\s*topResumedActivity=ActivityRecord\{{\d+ u0 {COMPONENT} t\d+\}}\s*', top),
                'unexpected foreground activity')
        s = state.summarize(sf, display, bl=raw_bl, thermal=thermal)
        therm = s['thermal']
        require((therm['service_status'], therm['service_override'], therm['brightness_throttling_status']) ==
                (0, False, 0) and s['hdr_modifier']['thermal_ratio_scale'] == 1,
                'thermal status, override or display throttling not normal')
        require(s['display_power'] == 'On' and
                s['hwc_dynamic_range'] == s['sdm_dynamic_range'] == scene.upper(),
                'current HWC and SDM dynamic ranges do not establish the requested scene')
        active = s['active_mode']
        require(active['hwc_id'] == hwc and active['sdm_config'] == hwc and
                active['vsync_hz'] == active['sdm_fps'] == hz,
                'actual SF/SDM mode or refresh differs from receipt')

        hdr = scene == 'hdr'
        ratio = s['display_hdr_sdr_ratio']
        hdr_mode = s['hdr_modifier']['mode']
        hbm = s['hbm']
        # A PQ output can be active without any brightness boost. Check and
        # report policy, but let current composition/ranges establish HDR.
        require(hdr_mode is not None and (hdr or hdr_mode == 'NO_HDR') and
                hbm['mode'] is not None and hbm['hdr_layer_present'] is hdr and
                hbm['force_hdr_layer_present'] is False and
                state.value(display, r'^ +mForceHdrLayerPresent=(true|false)[ \t]*$') == 'false' and
                ratio is not None and isfinite(ratio) and (ratio >= 1 if hdr else ratio == 1),
                'display HDR layer, brightness policy or HDR/SDR ratio disagrees')
        ident = state.value(sf, r'^Display (\d+) \(HWC display 0\):')
        sdm = state.block(sf, r'^SDM3 display_id: 0[ \t]*\n', r'^(?:SDM3 display_id:|OverlayProperties:)')
        video = video_evidence(sf, sdm, ident, scene)
    except ValueError as exc:
        raise ValueError(f'{stem}: {exc}') from None
    return dict(**video, hwc_dynamic_range=s['hwc_dynamic_range'], sdm_dynamic_range=s['sdm_dynamic_range'],
                hwc_id=active['hwc_id'], sf_refresh_hz=active['vsync_hz'], sdm_config=active['sdm_config'],
                sdm_fps=active['sdm_fps'], hdr_mode=hdr_mode, hbm_mode=hbm['mode']), ratio


def read_frames(path):
    entries = {}
    with original(path).open(newline='') as stream:
        rows = csv.DictReader(stream, strict=True)
        fields = rows.fieldnames or []
        require(set(FRAME_FIELDS) <= set(fields) and len(fields) == len(set(fields)),
                'frames.csv: missing or repeated column names')
        for row in rows:
            require(None not in row and None not in row.values() and re.fullmatch(PHASE, row['phase'])
                    and re.fullmatch(POS, row['frame_n']), f'frames.csv:{rows.line_num}: malformed frame row')
            key = row['phase'], int(row['frame_n'])
            require(key not in entries, f'frames.csv:{rows.line_num}: duplicate frame')
            entries[key] = row
    return entries


def bind_frame(path, size, ns, expected_us, group, label, row, seen_raw):
    try:
        data = original(path).read_bytes()
        require(len(data) == size, 'DNG byte count differs from receipt')
        raw, tags = decode_dng_bytes(data)
        m = extract_metadata(tags)
        require((m['make'], m['model'], m['iso'], m['width'], m['height'], m['orientation'],
                 m['cfa_pattern_2x2'], m['focal_length_mm'], raw.shape, m['white_level']) ==
                ('Nothing', 'A001', 6400, 4080, 3072, 1, [1, 2, 0, 1], 5.56, (3072, 4080), 1023),
                'wrong original DNG camera, ISO, geometry, CFA or lens')
        us = m['exposure_us']
        require(isfinite(us) and abs(1000 * us - ns) <= 1 and abs(us - expected_us) <= .001,
                'DNG exposure differs from receipt or phase')
        require((row['group'], row['scene'], row['cfa']) == (group, label, 'GBRG') and
                tuple(int(row[k]) for k in ('iso', 'width', 'height', 'orientation')) ==
                (m['iso'], m['width'], m['height'], m['orientation']) and
                tuple(int(row[k]) for k in ('y0', 'y1', 'x0', 'x1')) == ROI and
                float(row['focal_mm']) == m['focal_length_mm'] and
                abs(float(row['exposure_us']) - us) <= .001 and
                abs(float(row['black_dn']) - m['black_levels'][0]) <= 1e-6 and
                float(row['white_dn']) == m['white_level'],
                'frames.csv metadata differs from the original DNG or analysis ROI')
        # A metadata-only rewrite of an already counted RAW is not a new frame.
        digest = blake2b(raw.tobytes(order='C'), digest_size=16).digest()
        require(digest not in seen_raw, 'duplicate RAW plane')
        seen_raw.add(digest)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f'{path.stem}: {exc}') from None


def bind(archive, frames_csv, log=None):
    default_log = archive / 'acquisition.log'
    if not default_log.is_file():
        default_log = archive / 'run.log'  # a standalone, closed 30-fps snapshot
    full = log is None or log.resolve() == default_log.resolve()
    windows = list(read_windows(log if log is not None else default_log))
    require(len({w[-2] for w in windows}) == 1, 'windows do not share one verified wake epoch')
    phases = {w[0] for w in windows}
    keys = {(p, n) for p, *_, sizes in windows for n in range(1, len(sizes) + 1)}
    measured = read_frames(frames_csv)
    require(keys == measured.keys(), 'frames.csv inventory differs from the window receipts')
    names = {f'{p}__{n}.dng' for p, n in keys}
    present = {p.name for p in (archive / 'frames').iterdir()
               if p.name.lower().endswith(('.dng', '.partial')) and
               (full or p.name.rsplit('__', 1)[0] in phases)}
    require(present == names, 'unbound, unfinished or missing DNG in archive')
    for side in ('pre', 'post'):
        for suffix in SUFFIXES:
            ending = f'-{side}.{suffix}'
            found = {p.name[:-len(ending)] for p in archive.glob('*' + ending)}
            require((found if full else found & phases) == phases,
                    f'unbound or missing {ending} evidence')

    result, seen_raw = [], set()
    for phase, scene, bl, hwc, hz, ns, wake, sizes in windows:
        group, label, expected_us = phase_info(phase)
        # Scene tokens in the acquisition label are a sanity check, not proof.
        declared = {w.removesuffix('ret') for w in label.lower().split('_')} & {'sdr', 'hdr', 'pq'}
        if 'pq' in declared:
            declared.remove('pq')
            declared.add('hdr')
        require(not declared or declared == {scene}, f'{phase}: phase label contradicts the receipt scene')
        pre, ratio_pre = snapshot(archive, f'{phase}-pre', scene, bl, hwc, hz, wake)
        post, ratio_post = snapshot(archive, f'{phase}-post', scene, bl, hwc, hz, wake)
        require(pre == post and ratio_pre == ratio_post,
                f'{phase}: current video geometry or output state changed')
        for n, size in enumerate(sizes, 1):
            bind_frame(archive / 'frames' / f'{phase}__{n}.dng', size, ns, expected_us,
                       group, label, measured[phase, n], seen_raw)
        result.append(dict(phase=phase, group=group, scene=scene, sysfs_bl=bl, **pre,
                           hdr_sdr_ratio_pre=ratio_pre, hdr_sdr_ratio_post=ratio_post,
                           exposure_ns=ns, iso=6400, focal_mm=5.56, raw_width=4080, raw_height=3072,
                           roi_y0=ROI[0], roi_y1=ROI[1], roi_x0=ROI[2], roi_x1=ROI[3],
                           frames=len(sizes), bytes=sum(sizes), wake_epoch=wake, native_readbacks='none'))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    ap.add_argument('--log', type=Path, help='select a log by path or relative to ARCHIVE')
    args = ap.parse_args()
    log = args.log
    if log is not None and not log.is_absolute() and not log.is_file():
        log = args.archive / log
    try:
        rows = bind(args.archive, args.frames_csv, log)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
