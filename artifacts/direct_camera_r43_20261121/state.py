#!/usr/bin/env python3
"""Print sanitized current state for the built-in panel: python3 state.py PREFIX.

Inputs: .sf and .display; optional .bl (raw sysfs integer), .thermal and .layers.
A name-only layer list cannot establish visibility. Null means not established.
Historical HDR listener events are summarized separately, never used as state.
"""

import argparse
import json
import re
from pathlib import Path


NUM = r'-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?'
BOOL = r'true|false'
RANGE = r'SDR|HDR(?:10(?:\+|_PLUS)?|_PQ|_HLG)?|PQ|HLG|DOLBY_VISION'


def value(text, pattern, convert=str):
    """Require a unique value; conflicting or missing reports are unknown."""
    hits = set(re.findall(pattern, text, re.M))
    return convert(hits.pop()) if len(hits) == 1 else None


def block(text, start, stop):
    hits = list(re.finditer(start, text, re.M))
    if len(hits) != 1:
        return ''
    return re.split(stop, text[hits[0].end():], maxsplit=1, flags=re.M)[0]


def section(text, title):
    return block(text, '^' + re.escape(title) + r':[ \t]*\n', r'^\S')


def field(text, name, pattern=NUM, convert=float):
    return value(text, rf'^[ \t]*{re.escape(name)}[ \t]*[:=][ \t]*({pattern})[ \t]*$', convert)


def boolean(text, name):
    return field(text, name, BOOL, lambda x: x == 'true')


def physical(sf, disp_id):
    return block(sf, rf'^Display {disp_id} \(physical,[^\n]*\n',
                 r'^(?:Display \d+ \(|SurfaceFlinger global state:)')


def matrix(text):
    data = value(text, r'^\s*colorTransformMatrix=(\[\[[^\n]*?\]\])[ \t]*$')
    rows = re.findall(r'\[([^\[\]]+)\]', data or '')
    if len(rows) == 4 and all(re.fullmatch(rf'{NUM}(?:,{NUM}){{3}}', row) for row in rows):
        return [list(map(float, row.split(','))) for row in rows]
    return None


def region_visible(text):
    # Empty regions on this build often contain a single [0,0,0,0].
    m = re.search(r'^\s*Region visibleNonTransparentRegion \([^\n]*count=(\d+)\)\n'
                  r'((?:[ \t]*\[[\d ,\t-]+\][ \t]*\n)*)', text, re.M)
    if m:
        rects = re.findall(r'\[\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\]', m[2])
        if len(rects) == int(m[1]):
            return any(int(r) > int(l) and int(b) > int(t) for l, t, r, b in rects)
    return None


def transfer(ds):
    if ds is None:
        return None
    # Android Dataspace::TRANSFER_* is in bits 22..26, independent of range.
    return {1: 'LINEAR', 2: 'SRGB', 3: 'SMPTE_170M', 4: 'GAMMA2_2', 5: 'GAMMA2_6',
            6: 'GAMMA2_8', 7: 'PQ', 8: 'HLG'}.get((ds >> 22) & 31)


def layers(composition, sdm):
    expected = value(composition, r'^\s*(\d+) Layers?\s*$', int)
    parts = re.split(r'^\s*- Output Layer 0x[0-9a-f]+\(([^\n]*)\)[ \t]*$', composition, flags=re.M)
    # Match the same BufferQueue to its SF output layer, never an allocated buffer.
    hwc = {}
    for name, fmt, ds in re.findall(r'^layer: \d+ name:[ \t]*(.*?) z: -?\d+ [^\n]*?'
                                    r' format:[ \t]*(\S+) dataspace:(0x[0-9a-fA-F]+)\b', sdm, re.M):
        # SDM truncates long BufferQueue names, e.g. "...#9937(BLAST C".
        # Require the full SF layer name (including sequence), strip only the
        # recognized postfix or a truncated prefix of it.
        name = name.strip()
        m = re.fullmatch(r'(.*#\d+)(\(BLAST[^#]*)', name)
        if m and ('(BLAST Consumer)pid:'.startswith(m[2]) or re.fullmatch(r'\(BLAST Consumer\)pid:\d*', m[2])):
            name = m[1]
        hwc.setdefault(name, []).append((fmt.upper(), int(ds, 16)))
    out = []
    for name, text in zip(parts[1::2], parts[2::2]):
        ds = value(text, r'^[ \t]*forceClientComposition=[^\n]*? bufferTransform=[^\n]*?'
                         r' dataspace=[^\n]*? \((0x[\da-fA-F]+|\d+)\) whitePointNits=',
                   lambda x: int(x, 0))
        matches = hwc.get(name, [])
        fmt, hw_ds = matches[0] if len(matches) == 1 else ('', None)
        yuv = bool(re.search(r'YUV|Y_?CBCR|Y_?CRCB|NV(?:12|21)|[PT]010|TP10|VENUS|YV12', fmt))
        # SurfaceView alone also hosts games/UI. Only recognize video via a YUV
        # buffer or a specifically named video surface, not a player activity.
        video = yuv or bool(re.search(r'Video(?:Surface|View)|(?:SurfaceView|BLAST).*VideoDecoder', name, re.I))
        kind = 'video' if video else ('surface_view' if 'SurfaceView' in name else 'other')
        tr = transfer(ds)
        hw_tr = transfer(hw_ds)
        out.append({'kind': kind, 'visible': region_visible(text), 'yuv_buffer': yuv if fmt else None,
                    'buffer_format': fmt if re.fullmatch(r'(?:Y_CBCR|Y_CRCB|RGBA|RGBX|NV12|P010)(?:_[A-Z0-9]+)*', fmt) else None,
                    'sf_dataspace': f'0x{ds:08x}' if ds is not None else None, 'sf_transfer': tr,
                    'hwc_dataspace': f'0x{hw_ds:08x}' if hw_ds is not None else None,
                    'hwc_transfer': hw_tr})
    complete = expected is not None and len(out) == expected
    visible = [x for x in out if x['visible'] is True]
    video = [x for x in visible if x['kind'] == 'video']
    pq_video = None
    if any(x['sf_transfer'] == 'PQ' for x in video):
        pq_video = True
    elif complete and video and all(x['sf_transfer'] for x in video) and all(x['visible'] is not None for x in out):
        pq_video = False
    known = complete and all(x['visible'] is not None for x in out)
    return {'output_layer_count': expected, 'layers': out, 'visible_pq_video': pq_video,
            'visible_pq_tagged_layer_count': sum(x['sf_transfer'] == 'PQ' for x in visible)
            if known and all(x['sf_dataspace'] is not None for x in visible) else None}


def summarize(sf, display, layer_dump='', bl='', thermal=''):
    ident = value(sf, r'^Display (\d+) \(HWC display 0\):')
    comp = physical(sf, ident) or physical(layer_dump, ident)
    desc = block(sf, rf'^Display {ident}\n', r'^\S')
    power = field(desc, 'powerMode', r'On|Off|Doze|DozeSuspend', str)
    mode = value(desc, r'^[ \t]*activeMode=\{([^}\n]*)\}') or ''
    sdm = block(sf, r'^SDM3 display_id: 0[ \t]*\n', r'^(?:SDM3 display_id:|OverlayProperties:)')
    if power in ('Off', 'DozeSuspend') or re.search(r'^\s*isEnabled=false\b', comp, re.M):
        # The compositor may retain the last programmed layers/color mode.
        comp = sdm = ''
    events = block(sf, rf'^HDR events for display {ident}[ \t]*\n', r'^(?!\d+:)')
    counts = re.findall(r'^\d+: numHdrLayers\((\d+)\)', events, re.M)

    device = block(display, r'^  DisplayDeviceInfo\{"Built-in Screen":[^\n]*\n', r'^(?:  DisplayDeviceInfo\{|\S)')
    controllers = re.split(r'^Display Power Controller:[ \t]*$', display, flags=re.M)[1:]
    main = [c for c in controllers if re.search(r'^  mDisplayId=0$', c.split('Display Power Controller Locked State:')[0], re.M)]
    main = main[0] if len(main) == 1 else ''
    hbm = section(main, 'HighBrightnessModeController')
    hdr = section(main, 'HdrBrightnessModifier')
    clamp = section(main, 'BrightnessThermalClamper')
    backlight = section(main, 'Photonic Modulator State')

    return {
        **layers(comp, sdm),
        'display_power': power,
        'current_hdr_layer_count': field(hdr, 'mNumHdrLayers', r'\d+', int),
        'historical_hdr_layer_counts_seen': sorted(set(map(int, counts))),
        'hwc_dynamic_range': field(sdm, 'current dynamic_range', RANGE, str),
        'sdm_dynamic_range': value(sdm, rf'^Current Color Mode:[^\n]*? Dynamic[e]?_range ({RANGE})[ \t]*$'),
        'active_mode': {'hwc_id': value(mode, r'\bhwcId=(\d+)\b', int),
                        'vsync_hz': value(mode, rf'\bvsyncRate=({NUM}) Hz', float),
                        'group': value(mode, r'\bgroup=(0x[\da-fA-F]+|\d+)\b'),
                        'sdm_config': value(sdm, r'^num configs: \d+ active config index: (\d+)\b', int),
                        'sdm_fps': value(sdm, rf'^ FPS min:\S+ max:\S+ cur:({NUM})\b', float)},
        'sf_color_transform': matrix(comp),
        'sf_display_nits': value(comp, rf'^\s*displayBrightnessNits=({NUM})\b', float),
        'sf_sdr_white_nits': value(comp, rf'^\s*displayBrightnessNits=\S+ sdrWhitePointNits=({NUM})\b', float),
        'display_hdr_sdr_ratio': field(device, 'mCurrentHdrSdrRatio'),
        'hdr_modifier': {'mode': field(hdr, 'mMode', r'NO_HDR|NBM_HDR|HBM_HDR|HDR_NBM|HDR_HBM', str),
                         'max_desired_ratio': field(hdr, 'mMaxDesiredHdrRatio'),
                         'thermal_ratio_scale': field(hdr, 'mThermalHdrRatioScaleFactor')},
        'hbm': {'mode': value(hbm, rf'^[ \t]*mHbmMode=(off|hdr|sunlight)(?:\({NUM}\))?[ \t]*$'),
                'stats_state': field(hbm, 'mHbmStatsState', r'HBM_(?:OFF|ON_HDR|ON_SUNLIGHT)', str),
                'hdr_layer_present': boolean(hbm, 'mIsHdrLayerPresent'),
                'force_hdr_layer_present': boolean(hbm, 'mForceHdrLayerPresent')},
        'thermal': {'brightness_throttling_status': field(clamp, 'mThrottlingStatus', r'-?\d+', int),
                    'brightness_cap': field(clamp, 'mBrightnessCap'), 'cap_applied': boolean(clamp, 'mApplied'),
                    'service_status': field(thermal, 'Thermal Status', r'\d+', int),
                    'service_override': boolean(thermal, 'IsStatusOverride')},
        'sysfs_bl': int(bl.strip()) if re.fullmatch(r'\d{1,5}', bl.strip()) else None,
        'framework_actual_backlight': field(backlight, 'mActualBacklight'),
        'framework_actual_sdr_backlight': field(backlight, 'mActualSdrBacklight'),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('prefix')
    args = ap.parse_args()
    inputs = []
    for suffix in ('.sf', '.display', '.layers', '.bl', '.thermal'):
        try:
            inputs.append(Path(args.prefix + suffix).read_text(errors='replace'))
        except FileNotFoundError:
            if suffix in ('.sf', '.display'):
                ap.error('missing required ' + suffix + ' dump')
            inputs.append('')
        except OSError:
            ap.error('cannot read ' + suffix + ' dump')
    print(json.dumps(summarize(*inputs), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
