"""Offline replay of private Camera2 metadata and screenshots. No device access."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def load(root, name):
    return json.loads((root / (name + '.json')).read_text())


def replay(root):
    fixed = {'control.aeMode': 'OFF', 'control.afMode': 'OFF',
             'sensor.sensitivity': '6400', 'sensor.exposureTime': '500000',
             'lens.focusDistance': '6.69673395', 'control.zoomRatio': '1.00000000',
             'scaler.cropRegion': '0 0 4080 3072', 'control.captureIntent': 'PREVIEW'}
    rows = []
    frames, times = [], []
    for name in ('qualified1', 'qualified2', 'qualified3'):
        m = load(root, name + '_read0')
        need(m['camera'] == '0', 'unexpected camera')
        for k, v in fixed.items():
            need(m['req'].get(k) == v == m['res'].get(k), 'setting mismatch: ' + k)
        frames.append(int(m['res']['request.frameCount']))
        times.append(int(m['res']['sensor.timestamp']))
        with Image.open(root / (name + '.png')) as im:
            need(im.size == (1080, 2392), 'unexpected screenshot size')
            rgb = np.asarray(im.convert('RGB'))
        face = rgb[930:1340,80:575]
        trace = rgb[1080:1270,112:540]
        s_top = np.diff(np.median(rgb[947:994,200:315,1].astype(float), axis=1))
        s_right = np.diff(np.median(rgb[1008:1052,518:588,1].astype(float), axis=0))
        edge = [float(np.max(np.abs(a))) for a in (s_top,s_right)]
        need(min(edge) > 18 and face.max() < 255 and trace.max() < 250, 'edge/highlight gate')
        rows.append(dict(frame=frames[-1], face_max_rgb=face.max((0,1)).tolist(),
                         trace_max_rgb=trace.max((0,1)).tolist(), edges=edge,
                         trace_pixels=int(trace.shape[0] * trace.shape[1]),
                         zero_trace_per_channel=np.sum(trace == 0, axis=(0, 1)).tolist(),
                         any_zero_trace_pixels=int(np.sum((trace == 0).any(2))),
                         black_trace_pixels=int(np.sum((trace==0).all(2))),
                         black_face_pixels=int(np.sum((face==0).all(2)))))
    for a in (frames, times):
        need(all(x < y for x,y in zip(a,a[1:])), 'nonadvancing results')

    initial = load(root, 'oc_first')
    original_keys = ('control.aeMode control.afMode control.aeLock control.awbMode control.awbLock '
                     'lens.focusDistance sensor.sensitivity sensor.exposureTime control.zoomRatio '
                     'scaler.cropRegion flash.mode control.captureIntent lens.opticalStabilizationMode '
                     'control.videoStabilizationMode').split()
    need(initial['camera'] == '0', 'unexpected original camera')
    restored = [load(root, tag) for tag in
                ('oc_restored_all_read0', 'oc_restored_all_b_read0')]
    need(all(m['camera'] == '0' for m in restored), 'unexpected restore camera')
    for key in ('request.frameCount', 'sensor.timestamp'):
        need(int(restored[0]['res'][key]) < int(restored[1]['res'][key]),
             'OC restore nonadvancing: ' + key)
    for side in ('req','res'):
        need(initial[side].get('sensor.exposureTime')=='100000' and
             initial[side].get('lens.focusDistance')=='2.03874850', 'unexpected original')
        for restored_sample in restored:
            m = restored_sample[side]
            need(all(k in m and m[k]==initial[side].get(k) for k in original_keys), 'OC restore')
    stock=load(root,'stock_fresh_before_launch')
    stock_keys=('control.aeMode control.aeLock control.awbMode control.awbLock control.afMode '
                'lens.opticalStabilizationMode scaler.cropRegion control.zoomRatio control.aeRegions '
                'control.afRegions control.awbRegions control.aeExposureCompensation '
                'control.aeTargetFpsRange flash.mode control.captureIntent').split()
    final=[load(root,s) for s in ('stock_final0','stock_final_b0')]
    need(all(stock[k]==m[k] for k in stock_keys for m in final), 'Nothing restore')
    for key in ('request.frameCount', 'sensor.timestamp'):
        need(int(final[0][key]) < int(final[1][key]), 'stock preview stale: ' + key)
    log=[json.loads(l) for l in (root/'oc.log').read_text().splitlines()]
    need(any(k=='stock_controls_and_sole_restore' and v is True for _,k,v in log), 'missing ownership check')
    return dict(parameters=fixed, frames=rows, oc_observed_fields_restored=len(original_keys),
                nothing_control_fields_restored=len(stock_keys), hidden_pref_identity='not checked')


if __name__ == '__main__':
    print(json.dumps(replay(Path(sys.argv[1])), indent=2))
