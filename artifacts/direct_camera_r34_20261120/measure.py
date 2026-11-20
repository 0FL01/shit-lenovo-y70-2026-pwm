#!/usr/bin/env python3
"""Measure sanitized phase__N.dng files in a fixed native Bayer-cell ROI (R33).

With --flat-map, supply a JSON object mapping each short phase to the long
phase for the same scene, panel state and framing. Equal light must be checked
from the long-exposure DN measurements; the map does not establish it.
At least three independent, unclipped long captures are required. Each long
control uses the median of the *other* captures. Short frames use all of them.
Flat metrics describe spatial contrast at the recorded exposure, not PWM Hz.
"""

import argparse
import csv
import json
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'direct_camera_r33_20261120'))
from analyze import analyze, read_patch


LABEL = r'[A-Za-z0-9_]+'
NAME = re.compile(rf'({LABEL})__([0-9]+)\.dng')
MATCH_TAGS = ('iso', 'focal_mm', 'orientation', 'width', 'height', 'cfa')


def inputs(directory):
    frames = {}
    seen_files = set()
    for path in directory.iterdir():
        if path.suffix.lower() != '.dng':
            continue
        match = NAME.fullmatch(path.name)
        if not match or not path.is_file():
            raise ValueError('expected sanitized phase__N.dng inputs (ASCII letters, digits, underscores)')
        key = (match[1], int(match[2]))
        st = path.stat()
        identity = (st.st_dev, st.st_ino)
        if key in frames or identity in seen_files:
            raise ValueError('duplicate frame index or input file')
        frames[key] = path
        seen_files.add(identity)
    if not frames:
        raise ValueError('no phase__N.dng inputs')
    return frames


def load_map(path, phases):
    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError('duplicate phase in flat map')
        return dict(pairs)

    mapping = json.loads(path.read_text(), object_pairs_hook=unique)
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('flat map must be a nonempty JSON object: short phase -> long phase')
    for short, ref in mapping.items():
        if not all(isinstance(p, str) and re.fullmatch(LABEL, p) and p in phases for p in (short, ref)):
            raise ValueError('invalid or missing phase in flat map')
        if ref in mapping:
            raise ValueError('short and long phase sets must be disjoint')
    return mapping


def block_image(path, roi):
    _, green, _, _ = read_patch(path, roi)
    h, w = green.shape
    return green.reshape(h // 5, 5, w // 5, 5).mean(axis=(1, 3))


def reference_gate(refs):
    if len(refs) < 3:
        return 'too_few_references'
    first = refs[0][0]
    for row, blocks in refs:
        if any(row[k] is None or row[k] != first[k] for k in MATCH_TAGS):
            return 'reference_metadata_mismatch'
        if not np.isclose(row['exposure_us'], first['exposure_us'], rtol=.001, atol=0):
            return 'reference_exposure_mismatch'
        if row['raw_green_clip_frac']:
            return 'reference_clipped'
        if not np.all(blocks > 20):
            return 'reference_block_at_or_below_floor'
    return None


def correct(row, blocks, flat, n_used):
    ratios = blocks / flat
    p5, p95 = np.percentile(ratios, (5, 95))
    p1, p90 = np.percentile(ratios.mean(axis=1), (1, 90))
    if not (p95 + p5 > 0 and p90 > 0):
        row['flat_status'] = 'invalid_denominator'
        return
    row.update(flat_status='ok', flat_n_used=n_used,
               flat_block_contrast_pct=100 * (p95 - p5) / (p95 + p5),
               flat_row_p01_dip_pct=100 * (1 - p1 / p90))


def apply_flats(groups, mapping):
    for ref in sorted(set(mapping.values())):
        refs = groups[ref]
        rejection = reference_gate(refs)
        if not rejection:
            images = [blocks for _, blocks in refs]
            flat = np.median(images, axis=0)
        for i, (row, blocks) in enumerate(refs):
            row.update(flat_ref_phase=ref, flat_role='long_loo', flat_status=rejection)
            if not rejection:
                correct(row, blocks, np.median(images[:i] + images[i+1:], axis=0), len(refs) - 1)

        for short in sorted(k for k, v in mapping.items() if v == ref):
            for row, blocks in groups[short]:
                row.update(flat_ref_phase=ref, flat_role='short', flat_status=rejection)
                if rejection:
                    continue
                if any(row[k] != refs[0][0][k] for k in MATCH_TAGS):
                    row['flat_status'] = 'short_metadata_mismatch'
                elif row['exposure_us'] >= min(r['exposure_us'] for r, _ in refs):
                    row['flat_status'] = 'not_shorter_exposure'
                elif row['raw_green_clip_frac']:
                    row['flat_status'] = 'short_clipped'
                elif row['subfloor_lt20']:
                    row['flat_status'] = 'short_below_floor'
                else:
                    correct(row, blocks, flat, len(refs))


def measure(directory, roi, map_path):
    paths = inputs(directory)
    phases = sorted({phase for phase, n in paths})
    mapping = load_map(map_path, phases) if map_path else {}
    mapped = set(mapping) | set(mapping.values())
    groups = {p: [] for p in phases}
    ordinals = {p: i for i, p in enumerate(phases, 1)}
    for (phase, n), path in sorted(paths.items()):
        row = dict(phase=phase, phase_ordinal=ordinals[phase], frame_n=n, **analyze(path, roi))
        if mapping:
            row.update(flat_ref_phase=None, flat_role=None, flat_status='unmapped', flat_n_used=0,
                       flat_block_contrast_pct=None, flat_row_p01_dip_pct=None)
        groups[phase].append((row, block_image(path, roi) if phase in mapped else None))
    apply_flats(groups, mapping)
    return [row for group in groups.values() for row, _ in group]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('frames', type=Path)
    parser.add_argument('--roi', required=True, nargs=4, type=int, metavar=('Y0', 'Y1', 'X0', 'X1'))
    parser.add_argument('--flat-map', type=Path, help='JSON short phase -> long reference phase')
    args = parser.parse_args()
    try:
        rows = measure(args.frames, args.roi, args.flat_map)
    except OSError as exc:
        parser.error(exc.strerror)  # do not expose private input paths
    except ValueError as exc:
        parser.error(str(exc))
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
