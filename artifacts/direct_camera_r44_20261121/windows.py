#!/usr/bin/env python3
"""Bind closed R44 stock windows: python windows.py ARCHIVE frames.csv > windows.csv

Require the video alone on the physical output and in the current SDM layer
list at both boundaries. Use R43 receipts, native frames and geometry. .dc is
the actual panelDC sysfs value, .pref the provider value, and .wake the actual
wake epoch. same_surface_at_boundaries compares the observed layer sequence
numbers within one clip cycle. It does not establish uninterrupted playback.
These snapshots are neither continuous telemetry nor DDIC reads.
"""

import argparse
import csv
from math import isfinite
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121 import state, windows as r43


SUFFIXES = (*r43.SUFFIXES, 'dc', 'pref', 'wake')
DC = {'off': 0, 'on': 1, 'ret': 0}


def phase_intent(label, scene):
    # Accept underscore/camel-case labels or compact hdrOff/dcon forms. Do
    # not mistake incidental substrings (e.g. 'control' or 'offset') for intent.
    words = re.findall(r'[A-Za-z]+', re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', label))
    parts = []
    for word in words:
        match = re.fullmatch(r'(hdr|pq|sdr)?(?:dc)?(off|on|ret)', word.lower())
        parts.extend(filter(None, match.groups()) if match else [word.lower()])
    intents = [w for w in parts if w in DC]
    r43.require(len(intents) == 1, f'{label}: expected exactly one DC intent (off, on or ret)')
    declared = {'hdr' if w == 'pq' else w for w in parts if w in ('hdr', 'pq', 'sdr')}
    r43.require(not declared or declared == {scene}, f'{label}: scene label contradicts receipt')
    return intents[0]


def clip_cycle(group, phase):
    if group in ('day', 'cal'):
        return 'low' if 'Low' in phase else 'high'
    if group in ('even', 'black'):
        return group
    raise ValueError(f'{phase}: no clip cycle defined for group {group}')


def current_surface_id(sdm):
    # Count every current row before parsing the video. Filtering for the
    # player first would silently discard overlays and malformed layer rows.
    active, separator, _ = sdm.partition('----------Color Modes---------')
    r43.require(separator, 'missing SDM current layer list boundary')
    rows = [line for line in active.splitlines() if line.lstrip().startswith('layer:')]
    r43.require(len(rows) == 1, f'expected only the current SDM video layer, found {len(rows)} layers')
    layer = r43.LAYER.fullmatch(rows[0])
    surface = layer and re.match(r43.SURFACE, layer[1])
    r43.require(surface, 'sole current SDM layer is not the player SurfaceView')
    return int(surface[0].rsplit('#', 1)[1])


def snapshot(archive, stem, scene, bl, hwc, hz, wake, intent):
    def text(suffix):
        return r43.original(archive / f'{stem}.{suffix}').read_text()

    def check(ok, why):
        r43.require(ok, f'{stem}: {why}')

    session = text('session').strip().splitlines()
    # status_session reports the live worker lock on line 1. A saved reason
    # such as "stopped: stock registers verified" is not a current readback.
    check(session and session[0] == 'inactive' and
          not any(re.search(r'\brunning\b', line, re.I) for line in session),
          'expected inactive session status with no running worker')
    dc, pref = text('dc').strip(), text('pref').strip()
    check(dc in ('0', '1') and pref in ('0', '1'), 'expected binary panelDC and provider reads')
    check(dc == pref == str(DC[intent]), f'panelDC={dc}, provider={pref}, expected {intent}')
    check(text('wake').strip() == str(wake), 'wake epoch differs from receipt')
    raw_bl = text('bl').strip()
    check(raw_bl == str(bl), 'sysfs BL differs from receipt')
    check(re.fullmatch(rf'\s*topResumedActivity=ActivityRecord\{{\d+ u0 {r43.COMPONENT} t\d+\}}\s*',
                       text('top')), 'unexpected foreground activity')

    sf, display = text('sf'), text('display')
    s = state.summarize(sf, display, bl=raw_bl, thermal=text('thermal'))
    therm, hdr, hbm = s['thermal'], s['hdr_modifier'], s['hbm']
    check((therm['service_status'], therm['service_override'], therm['brightness_throttling_status']) ==
          (0, False, 0) and hdr['thermal_ratio_scale'] == 1, 'thermal override or throttling not normal')
    check(s['display_power'] == 'On' and s['hwc_dynamic_range'] == s['sdm_dynamic_range'] == scene.upper(),
          'current display power or HWC/SDM range disagrees')
    active = s['active_mode']
    check(active['hwc_id'] == active['sdm_config'] == hwc and active['vsync_hz'] == active['sdm_fps'] == hz,
          'actual SF/SDM mode or refresh differs from receipt')
    ratio = s['display_hdr_sdr_ratio']
    is_hdr = scene == 'hdr'
    check(hdr['mode'] is not None and (is_hdr or hdr['mode'] == 'NO_HDR') and
          hbm['mode'] is not None and hbm['hdr_layer_present'] is is_hdr and
          hbm['force_hdr_layer_present'] is False and
          state.value(display, r'^ +mForceHdrLayerPresent=(true|false)[ \t]*$') == 'false' and
          ratio is not None and isfinite(ratio) and (ratio >= 1 if is_hdr else ratio == 1),
          'display HDR layer, brightness policy or HDR/SDR ratio disagrees')
    ident = state.value(sf, r'^Display (\d+) \(HWC display 0\):')
    sdm = state.block(sf, r'^SDM3 display_id: 0[ \t]*\n', r'^(?:SDM3 display_id:|OverlayProperties:)')
    layers = s['layers']
    check(s['output_layer_count'] == len(layers) and all(layer['visible'] is not None for layer in layers),
          'incomplete physical output layer inventory or unknown visibility')
    visible = sum(layer['visible'] for layer in layers)
    check(visible == 1, f'expected only the video visible on the physical output, found {visible} layers')
    try:
        surface_id = current_surface_id(sdm)
        # Binds the sole SDM row to a visible full-field output of the same name.
        video = r43.video_evidence(sf, sdm, ident, scene)
    except ValueError as exc:
        raise ValueError(f'{stem}: {exc}') from None
    return dict(**video, display_power=s['display_power'], sysfs_bl=int(raw_bl),
                hwc_dynamic_range=s['hwc_dynamic_range'], sdm_dynamic_range=s['sdm_dynamic_range'],
                hwc_id=active['hwc_id'], sf_refresh_hz=active['vsync_hz'], sdm_config=active['sdm_config'],
                sdm_fps=active['sdm_fps'], hdr_mode=hdr['mode'], hbm_mode=hbm['mode'],
                hdr_layer_present=hbm['hdr_layer_present'], thermal_status=therm['service_status'],
                thermal_override=therm['service_override'],
                brightness_throttling_status=therm['brightness_throttling_status'],
                thermal_ratio_scale=hdr['thermal_ratio_scale'], session_status=session[0], wake_epoch=wake,
                panel_dc=int(dc), pref=int(pref), hdr_sdr_ratio=ratio), surface_id


def bind(archive, frames_csv):
    windows = list(r43.read_windows(archive / 'acquisition.log'))
    r43.require(len({w[-2] for w in windows}) == 1, 'windows span multiple wake epochs')
    phases = {w[0] for w in windows}
    for side in ('pre', 'post'):
        for suffix in SUFFIXES:
            ending = f'-{side}.{suffix}'
            found = {p.name.removesuffix(ending) for p in archive.glob('*' + ending)}
            r43.require(found == phases, f'unbound or missing {ending} evidence')
    measured = r43.read_frames(frames_csv)
    keys = {(p, n) for p, *_, sizes in windows for n in range(1, len(sizes) + 1)}
    r43.require(keys == measured.keys(), 'frames.csv inventory differs from receipts')
    frames = archive / 'frames'
    present = {p.name for p in frames.iterdir() if p.name.lower().endswith(('.dng', '.partial'))}
    r43.require(present == {f'{p}__{n}.dng' for p, n in keys}, 'unbound, missing or unfinished DNG')

    result, seen_raw, surfaces = [], set(), {}
    for phase, scene, bl, hwc, hz, ns, wake, sizes in windows:
        group, label, expected_us = r43.phase_info(phase)
        intent = phase_intent(f'{group}_{label}', scene)
        (pre, pre_id), (post, post_id) = (snapshot(archive, f'{phase}-{side}', scene, bl, hwc, hz, wake, intent)
                                          for side in ('pre', 'post'))
        r43.require(pre_id == post_id, f'{phase}: video SurfaceView changed across window')
        surfaces.setdefault(clip_cycle(group, phase), set()).add(pre_id)
        for k in pre:
            r43.require(pre[k] == post[k], f'{phase}: {k} changed across window')
        for n, size in enumerate(sizes, 1):
            r43.bind_frame(frames / f'{phase}__{n}.dng', size, ns, expected_us,
                           group, label, measured[phase, n], seen_raw)
        # Keep the actual reads on both sides explicit in the public CSV.
        separate = ('panel_dc', 'pref', 'hdr_sdr_ratio')
        boundary = {f'{k}_{side}': snap[k] for k in separate
                    for side, snap in (('pre', pre), ('post', post))}
        common = {k: v for k, v in pre.items() if k not in separate}
        y0, y1, x0, x1 = r43.ROI
        result.append(dict(phase=phase, group=group, scene=scene, dc_label=intent, **boundary, **common,
                           exposure_ns=ns, iso=6400, focal_mm=5.56, raw_width=4080, raw_height=3072,
                           roi_y0=y0, roi_y1=y1, roi_x0=x0, roi_x1=x1, frames=len(sizes),
                           bytes=sum(sizes), native_readbacks='none'))
    for row in result:
        row['same_surface_at_boundaries'] = len(surfaces[clip_cycle(row['group'], row['phase'])]) == 1
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    ap.add_argument('frames_csv', metavar='frames.csv', type=Path)
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.frames_csv)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
