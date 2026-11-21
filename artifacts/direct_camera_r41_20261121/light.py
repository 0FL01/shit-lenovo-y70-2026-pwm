#!/usr/bin/env python3
"""R41 signed, camera-relative Y proxy (DN): python light.py FRAMES PHASE.

Adobe DNG Specification 1.4, ch. 6 (Mapping Camera Color Space to CIE XYZ):
for column vectors, individual-camera RGB = M @ XYZ at the calibration white,
M = diag(AnalogBalance) @ CameraCalibration @ ColorMatrix. Therefore the Y
row for black-subtracted native camera RGB is row 1 (zero-based) of inv(M).
Use the D65 endpoint as a fixed daylight/display-white reference for *all*
fields, not a white point estimated from their color. Normalize the row to sum
to one: an equal R,G,B signal of d DN gives d proxy DN. No AsShotNeutral,
second white balance, ForwardMatrix (which expects white-balanced values),
chromatic adaptation, demosaic, gamma or per-frame brightness normalization.

The two ColorMatrices below were read from Nothing A001 R36 DNGs. The two
CameraCalibrations are identity, and missing AnalogBalance defaults to ones.
This is a native sensor ROI, before the optional lens-shading gain maps. Match
camera, framing/ROI, ISO and exposure between phases. BlackLevel subtraction
removes the electronic offset, not ambient light or the display's black field.
Broadband chart calibration is not a spectral measurement of OLED primaries:
the signed B weight can even yield a negative estimate. Equal camera proxy DN
does not establish equal human photopic luminance; there is no cd/m² scale.
"""

import argparse
from pathlib import Path
import re
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'night_r113_camera_notch'))
from dng_qualify import _read_ifd, decode_dng_bytes, extract_metadata


ROI = (630, 1370, 540, 720)  # y0,y1,x0,x1; half-open native 2x2 Bayer cells
_CM1 = np.array([[43699, -10413, -5619], [-37614, 91081, 9373],
                 [-9036, 17377, 39559]]) / 65536
_CM2 = np.array([[100366, -30776, -14094], [-31210, 94721, 439],
                 [-4702, 15645, 15267]]) / 65536
_PROFILE_TAGS = {50721, 50722, 50723, 50724, 50727, 50778, 50779}


def rgb_weights(tags):
    """Return signed (R,G,B) weights after checking the frame's fixed R36 profile."""
    eye = np.eye(3).ravel()
    for tag, name, expected, default in (
        (50778, 'CalibrationIlluminant1 (D65)', [21], None),
        (50779, 'CalibrationIlluminant2 (Standard Light A)', [17], None),
        (50721, 'ColorMatrix1', _CM1.ravel(), None),
        (50722, 'ColorMatrix2', _CM2.ravel(), None),
        (50723, 'CameraCalibration1', eye, eye),
        (50724, 'CameraCalibration2', eye, eye),
        (50727, 'AnalogBalance', [1, 1, 1], [1, 1, 1]),
    ):
        if not np.array_equal(tags.get(tag, default), expected):
            raise ValueError(f'{name} missing or inconsistent with fixed A001 profile')
    cm = np.asarray(tags[50721]).reshape(3, 3)
    cc = np.asarray(tags.get(50723, eye)).reshape(3, 3)
    m = np.diag(tags.get(50727, [1, 1, 1])) @ cc @ cm
    y = np.linalg.solve(m.T, [0., 1., 0.])
    return tuple(map(float, y / y.sum()))


def read_dng(path):
    """Return (native RAW, numeric TIFF tags including the embedded IFD0 profile)."""
    data = Path(path).read_bytes()
    raw, tags = decode_dng_bytes(data)
    # The strict shared decoder validates the TIFF header and RAW, but by
    # design its tag allowlist omits the IFD0 camera color profile.
    endian = '<' if data[:2] == b'II' else '>'
    ifd0 = struct.unpack_from(endian + 'I', data, 4)[0]
    extra, _ = _read_ifd(data, endian, ifd0, _PROFILE_TAGS | {33437})
    tags.update(extra)
    return raw, tags


def signal(raw, tags, roi=ROI, block=5):
    """Return (signed mean DN, 2D block means); block=1 retains each Bayer cell."""
    m = extract_metadata(tags)
    if ((m['make'], m['model'], m['focal_length_mm'], tags.get(33437), m['iso'],
         m['orientation'], m['width'], m['height'], m['cfa_pattern_2x2'], m['white_level']) !=
            ('Nothing', 'A001', 5.56, [1.87], 6400, 1, 4080, 3072, [1, 2, 0, 1], 1023)):
        raise ValueError('wrong camera, optics, ISO, orientation, RAW geometry or DN scale')
    if raw.shape != (m['height'], m['width']):
        raise ValueError('RAW dimensions disagree with DNG metadata')
    weights = rgb_weights(tags)
    y0, y1, x0, x1 = roi
    h, w = y1-y0, x1-x0
    if not (0 <= y0 < y1 <= raw.shape[0]//2 and 0 <= x0 < x1 <= raw.shape[1]//2):
        raise ValueError('ROI outside native Bayer-cell bounds')
    if not isinstance(block, int) or block < 1 or h % block or w % block:
        raise ValueError('block must be a positive integer dividing both ROI extents')

    blocks = np.zeros((h//block, w//block), dtype=np.float64)
    for i, color in enumerate(m['cfa_pattern_2x2']):
        dy, dx = divmod(i, 2)
        plane = raw[2*y0+dy:2*y1:2, 2*x0+dx:2*x1:2]
        if plane.max() >= m['white_level'] or plane.min() == 0:
            raise ValueError(f'CFA site {i} ({"RGB"[color]}) hits white or storage floor in ROI')
        # A 2x2 cell supplies one R, two Gs (averaged) and one B. Preserve
        # sub-black samples and negative combinations, including in dark frames.
        means = plane.reshape(h//block, block, w//block, block).mean(axis=(1, 3))
        blocks += (means - m['black_levels'][i]) * (weights[color] / (2 if color == 1 else 1))
    return float(blocks.mean()), blocks


def frame_signal(path, roi=ROI, block=5):
    """Measure one DNG; ROI and block sizes use native Bayer-cell coordinates."""
    return signal(*read_dng(path), roi=roi, block=block)


def phase_signal(frames, phase):
    """Median of per-DNG means, with one exposure and contiguous indices from 1."""
    pattern = re.compile(re.escape(phase) + r'__([0-9]+)\.dng')
    inputs = sorted((int(m[1]), p) for p in Path(frames).iterdir()
                    if (m := pattern.fullmatch(p.name)))
    if not inputs:
        raise ValueError(f'no {phase}__N.dng frames')
    if [n for n, _ in inputs] != list(range(1, len(inputs)+1)):
        raise ValueError(f'{phase}: duplicate or missing frame index; expected 1..N')
    means, exposure = [], None
    for _, path in inputs:
        try:
            raw, tags = read_dng(path)
            if exposure is not None and exposure != tags[33434]:
                raise ValueError('mixed exposure times within phase')
            exposure = tags[33434]
            means.append(signal(raw, tags)[0])
        except (ValueError, OSError) as exc:
            raise ValueError(f'{path.name}: {exc}') from exc
    return float(np.median(means))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('frames', metavar='FRAMES', type=Path, help='directory containing PHASE__N.dng')
    cli.add_argument('phase', metavar='PHASE')
    args = cli.parse_args()
    try:
        print(f'{phase_signal(args.frames, args.phase):.12g}')
    except (ValueError, OSError) as exc:
        cli.error(str(exc))
