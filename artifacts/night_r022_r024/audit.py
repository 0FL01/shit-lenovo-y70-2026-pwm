"""R022–R024: read only archived files. No acquisition or network."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ART = HERE.parent
R11 = ART / 'stock_expert_direct_r11_20261118'
SAMPLES = ('short_drag', 'short2', 'short3', 'short4')
spec = importlib.util.spec_from_file_location('r12_source', ART / 'stock_gc08a8_timing_r12_20261118/audit.py')
r12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r12)


def check(b, why):
    if not b:
        raise ValueError(why)


def read_json(p):
    return json.loads(p.read_text())


def partition(rows):
    slots = {f'p{i:02}_{j}.png' for i in range(1, 7) for j in range(1, 4)}
    check(set(rows) == slots, 'missing/additional R12b slot')
    counts = Counter()
    for v in rows.values():
        check(v['role'] in {'U', 'C', 'c', 'D', 'd'}, 'unrecognized role')
        for k in ['original_signal_pass', 'geometry_pass']:
            check(type(v[k]) is bool, 'nonboolean gate')
        if v['role'] != 'U':
            counts[(v['original_signal_pass'], v['geometry_pass'])] += 1
    check(sum(counts.values()) == 15, 'coded denominator')
    return {k: counts[pair] for k, pair in [('both_pass', (True, True)), ('signal_only_fails', (False, True)),
                                           ('geometry_only_fails', (True, False)), ('both_fail', (False, False))]}


def one(pattern, text):
    hits = re.findall(pattern, text, re.M)
    check(len(hits) == 1, 'missing/ambiguous ' + pattern)
    return hits[0]


def ui(text):
    check(text.startswith('ACTIVITY com.nothing.camera/'), 'wrong activity')
    config = one(r'^\s*mCurrentConfig=(.*)$', text)
    return dict(display_rotation=one(r'\bmDisplayRotation=(ROTATION_\d+)\b', config),
                orientation=one(r'\b(port|land)\b', config),
                app_bounds=list(map(int, one(r'mAppBounds=Rect\((\d+), (\d+) - (\d+), (\d+)\)', config))),
                render_frame_parent_rect=list(map(int, one(r'^.*PreviewFrameLayout\{[^\n]*? (\d+),(\d+)-(\d+),(\d+) #[^\n]* app:id/render_frame\}$', text))))


def streams(dynamic):
    block = r12.section(dynamic, '    Stream configuration:', '    Camera3 Buffer Manager:')
    op = int(one(r'^\s*Operation mode: CUSTOM \((\d+)\)', block))
    parts = re.split(r'^\s*Stream\[(\d+)\]: Output\s*$', block, flags=re.M)
    rows = []
    for index, desc in zip(parts[1::2], parts[2::2]):
        consumer = one(r'^\s*Consumer name: (SurfaceTexture|ImageReader)-[^\n]+$', desc)
        w, h, fmt = one(r'^\s*Dims: (\d+) x (\d+), format (0x[0-9a-f]+),', desc)
        produced = int(one(r'^\s*Frames produced: (\d+),', desc))
        rows.append(dict(index=int(index), consumer=consumer, size=[int(w), int(h)], format=fmt, frames_produced=produced))
    check([s['index'] for s in rows] == list(range(5)), 'stream inventory')
    return op, rows


def classify(src, dst):
    # Dimensions only, not a prediction of ISP policy, field of view or mode.
    w, h = src
    x, y = dst
    if (w, h) == (x, y):
        return 'equal_size'
    if w*y == h*x:
        return 'uniform_scale_' + str(Fraction(x, w))
    return 'aspect_change_required'


def run(archive, driver):
    counts = partition(read_json(ART / 'night_r016_r018_20261118/outcome.json')['R018'])
    series = read_json(ART / 'night_r019_r021/result.json')['R020']
    check(sum(counts.values()) == series['coded_total'] and counts['both_pass'] == series['joint_coded_pass'], 'prior audits disagree')
    source = driver.read_bytes()
    check(hashlib.sha256(source).hexdigest() == r12.PUBLIC_HASH, 'unrecognized driver source')
    modes, _ = r12.source_tables(source.decode())
    pins = read_json(R11 / 'private_evidence_hashes.json')
    samples = {}
    for tag in SAMPLES:
        def pinned(suffix):
            name = tag + suffix
            data = (archive/name).read_bytes()
            check(hashlib.sha256(data).hexdigest() == pins[name], 'R11 identity: ' + name)
            return data
        raw = pinned('_raw.txt').decode()
        png = pinned('.png')
        check(png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR', 'not PNG')
        uitxt = (archive/(tag+'.ui.txt')).read_bytes()
        dynamic = r12.section(raw, '== Camera device 2 dynamic info: ==', '== Camera device 3 dynamic info: ==')
        static = r12.section(raw, '== Camera HAL device device@1.1/internal/2 (v1.2) static information: ==', 'dumpState:')
        sensor = r12.extract_dump(raw)
        op, rows = streams(dynamic)
        actual = r12.section(dynamic, 'Latest received frame:', 'Device status:')
        scenario_present = re.search(r'^\s*com\.mediatek\.seamlessfeature\.sensorScenario \(', actual, re.M) is not None
        check(not scenario_present, 'explicit current scenario needs fresh interpretation')
        samples[tag] = dict(ui=ui(uitxt.decode()), ui_snapshot_sha256=hashlib.sha256(uitxt).hexdigest(),
                            screenshot_size=list(struct.unpack('>II', png[16:24])), sensor_orientation=int(r12.field(static, 'sensor.orientation')),
                            active_rect=sensor['active_rect'], result_crop=list(map(int, r12.field(actual, 'scaler.cropRegion').split())),
                            mode=op, streams=rows)
    def schema(s):
        return {**{k:v for k,v in s.items() if k not in ('streams', 'ui_snapshot_sha256')},
                'streams': [{**{k:v for k,v in x.items() if k != 'frames_produced'}, 'used':x['frames_produced']>0} for x in s['streams']]}
    ref = samples[SAMPLES[0]]
    check(all(schema(s) == schema(ref) for s in samples.values()), 'changed geometry/stream use across samples')
    matrix = {k:{'source_output':[v['w2_tg_size'],v['h2_tg_size']], 'y1_offset':v['y1_offset'],
                 'to_stream_by_index':[classify((v['w2_tg_size'],v['h2_tg_size']),s['size']) for s in ref['streams']]}
              for k,v in modes.items()}
    return dict(R022=dict(coded=counts, completed_series=series['independent_completed_series'], accepted_series=series['series_pass']),
                R023=dict(samples=samples, buffer_to_view_matrix=None, readout_axis_sign=None),
                R024=dict(public_commit=r12.SHA, public_mode_geometry=matrix, selected_sensor_scenario=None, installed_driver_equivalence=None))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_r11_archive', type=Path)
    parser.add_argument('public_driver_file', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.private_r11_archive, args.public_driver_file), indent=2))
