#!/usr/bin/env python3
"""Strict, offline Camera2 dumpsys snapshot validation for optical trials.

No ADB/device calls. Select one active Open Camera client, then distinguish its
latest received result from its last logical request. A passing pair of snapshots
qualifies observed settings/stream progress, NOT every encoded frame or optical Hz.
Unknown dump layouts fail closed. Do not pass preview as previous for recording:
the stream configuration and sensor skew can legitimately change at that boundary.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any


class CaptureMetadataError(ValueError):
    """Missing, ambiguous, stale or unexpected capture evidence."""


FIELDS = {
    'exposure_ns': ('android.sensor.exposureTime', int, 1),
    'iso': ('android.sensor.sensitivity', int, 1),
    'ae_mode': ('android.control.aeMode', str, 1),
    'af_mode': ('android.control.afMode', str, 1),
    'focus_diopters': ('android.lens.focusDistance', float, 1),
    'crop': ('android.scaler.cropRegion', int, 4),
    'zoom': ('android.control.zoomRatio', float, 1),
    'eis_mode': ('android.control.videoStabilizationMode', str, 1),
    'ois_mode': ('android.lens.opticalStabilizationMode', str, 1),
    'capture_intent': ('android.control.captureIntent', str, 1),
    'request_id': ('android.request.id', int, 1),
    'frame_duration_ns': ('android.sensor.frameDuration', int, 1),
    'frame_count': ('android.request.frameCount', int, 1),
    'timestamp_ns': ('android.sensor.timestamp', int, 1),
    'rolling_shutter_skew_ns': ('android.sensor.rollingShutterSkew', int, 1),
}
RESULT_ONLY = {'frame_count', 'timestamp_ns', 'rolling_shutter_skew_ns'}
ENCODER_CONSUMERS = {'GraphicBufferSource', 'CameraSource', 'MediaRecorder'}


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise CaptureMetadataError(message)


def _one(pattern: str, text: str, label: str, flags: int = re.M) -> Any:
    matches = re.findall(pattern, text, flags)
    _need(len(matches) == 1, f'Expected exactly one {label}')
    return matches[0]


def _between(text: str, start: str, end: str, label: str) -> str:
    _need(text.count(start) == text.count(end) == 1, f'Ambiguous {label} boundaries')
    left = text.index(start) + len(start)
    right = text.index(end)
    _need(right > left, f'Reversed {label} boundaries')
    return text[left:right]


def _selected_scope(text: str, camera_id: str) -> tuple[str, str]:
    _need(isinstance(text, str) and len(text) <= 8 * 1024 * 1024, 'Invalid dump input')
    markers = list(re.finditer(r'^== Camera device (\S+) dynamic info: ==\s*$', text, re.M))
    selected = [i for i, marker in enumerate(markers) if marker[1] == camera_id]
    _need(len(selected) == 1, 'Expected one selected camera dynamic section')
    index = selected[0]
    marker = markers[index]
    return (text[marker.end():markers[index + 1].start() if index + 1 < len(markers) else None],
            text[:marker.start()])


def _metadata(section: str, *, result: bool) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, (tag, converter, count) in FIELDS.items():
        if not result and name in RESULT_ONLY:
            continue
        pattern = (r'^\s*' + re.escape(tag)
                   + r'\s+\([0-9a-fA-F]+\):\s+\w+\[(\d+)\][ \t]*\n'
                   + r'[ \t]*\[([^\]\n]+)\][ \t]*$')
        length, raw = _one(pattern, section, f'{name} in ' + ('result' if result else 'request'))
        tokens = raw.split()
        _need(int(length) == count and len(tokens) == count, f'Wrong length for {name}')
        try:
            values = [converter(v) for v in tokens]
        except (ValueError, OverflowError) as error:
            raise CaptureMetadataError(f'Invalid value for {name}') from error
        _need(all(not isinstance(v, float) or math.isfinite(v) for v in values),
              f'Non-finite value for {name}')
        output[name] = values[0] if count == 1 else values
    return output


def _streams(device: str, request_ids: list[int]) -> list[dict[str, Any]]:
    stream_part = _between(device, '    Stream configuration:\n',
                           '    Camera3 Buffer Manager:\n', 'stream configuration')
    markers = list(re.finditer(r'^    Stream\[(\d+)\]: Output\s*$', stream_part, re.M))
    _need(bool(markers), 'No output streams')
    streams = []
    for index, marker in enumerate(markers):
        block = stream_part[marker.end():markers[index + 1].start() if index + 1 < len(markers) else None]
        stream_id = int(marker[1])
        consumer = _one(r'^\s*Consumer name: (.+)$', block, 'stream consumer').strip()
        width, height, pixel_format = _one(
            r'^\s*Dims: (\d+) x (\d+), format (0x[0-9a-fA-F]+),[^\n]*$', block, 'stream dimensions')
        produced, timestamp = _one(
            r'^\s*Frames produced: (\d+), last timestamp: (\d+) ns\s*$', block, 'stream progress')
        state = int(_one(r'^\s*State: (\d+)\s*$', block, 'stream state'))
        # Do not copy PID/address-bearing consumer strings into trial summaries.
        consumer_kind = consumer if consumer in ENCODER_CONSUMERS else (
            'SurfaceTexture' if consumer.startswith('SurfaceTexture') else
            'ImageReader' if consumer.startswith('ImageReader') else 'unknown')
        streams.append({'id': stream_id, 'width': int(width), 'height': int(height),
                        'pixel_format': pixel_format.lower(), 'state': state,
                        'consumer_kind': consumer_kind, 'frames_produced': int(produced),
                        'last_timestamp_ns': int(timestamp), 'requested': stream_id in request_ids})
    ids = [stream['id'] for stream in streams]
    _need(len(ids) == len(set(ids)) and set(request_ids) <= set(ids), 'Ambiguous output stream IDs')
    return streams


def validate_capture(
    text: str, previous: dict[str, Any] | None = None, *,
    exposure_ns: int = 100000, iso: int = 6400,
    focus_diopters: float = 2.03874850, crop: tuple[int, ...] = (0, 0, 4080, 3072),
    zoom: float = 1.0, camera_id: str = '0',
    expected_size: tuple[int, int] | None = None, require_recording: bool = False,
    expected_fps: float = 30.0,
) -> dict[str, Any]:
    """Validate current request/result and optional progress from the same session.

    `previous` must come from this function under the same recording configuration.
    Exposure/ISO may change when explicitly passed; crop, focus, zoom, skew and
    output streams must not. Compare two settled snapshots after starting recording
    before the first trial hold. Never use encoded PTS as sensor timestamps.
    """
    _need(isinstance(text, str) and len(text) <= 8 * 1024 * 1024, 'Invalid dump input')
    _need(type(exposure_ns) is int and exposure_ns > 0 and type(iso) is int and iso > 0,
          'Invalid expected exposure or ISO')
    _need(math.isfinite(expected_fps) and expected_fps > 0, 'Invalid expected FPS')
    _need(math.isfinite(focus_diopters) and math.isfinite(zoom) and zoom > 0,
          'Invalid expected lens profile')
    _need(len(crop) == 4 and all(type(v) is int for v in crop), 'Invalid expected crop')
    if expected_size is not None:
        _need(len(expected_size) == 2 and all(type(v) is int and v > 0 for v in expected_size),
              'Invalid expected stream size')
    if require_recording and expected_size is None:
        expected_size = (1280, 720)

    scope, prefix = _selected_scope(text, camera_id)
    # Never accept a static/provider metadata block as an active client dump.
    _need('Active Camera Clients:' in prefix, 'Missing active-client list')
    active = re.findall(r'^\(Camera ID: ([^,]+),[^\n]*Client Package Name: ([^,]+),',
                        prefix, re.M)
    _need(active == [(camera_id, 'net.sourceforge.opencamera')], 'Unexpected active camera client')
    package = _one(r'^    Client package: ([^\s]+)\s*$', scope, 'client package')
    _need(package == 'net.sourceforge.opencamera', 'Unexpected camera package')
    client_id, client_address = _one(r'^  CameraDeviceClient\[([^\]]+)\] \(([^)]+)\) dump:\s*$',
                                   scope, 'camera client instance')
    _need(client_id == camera_id, 'Camera client section mismatch')
    client_pid = _one(r'^    Client PID: (\d+)\s*$', scope, 'client process')
    result_part = _between(scope, '    Latest received frame:\n', '  Device dump:\n', 'result')
    device = scope.split('  Device dump:\n', 1)[1]
    status = _one(r'^    Device status: ([A-Z_]+)\s*$', device, 'device status')
    _need(status == 'ACTIVE', 'Camera is not active')
    request_prefix = _between(device, '    Last request sent:\n',
                              '    Logical request settings:\n', 'last request')
    _need(re.match(r'^      Output Stream Ids:\n(?:[ \t]+\d+\n)+\s*$', request_prefix) is not None,
          'Unknown last-request stream layout')
    request_ids = [int(value) for value in re.findall(r'^\s+(\d+)\s*$', request_prefix, re.M)]
    _need(len(request_ids) == len(set(request_ids)), 'Duplicate requested stream')
    request_part = _between(device, '    Logical request settings:\n',
                            '     HAL device dump:\n', 'request metadata')
    _need('Physical request' not in request_part, 'Unsupported physical-camera request metadata')
    result = _metadata(result_part, result=True)
    request = _metadata(request_part, result=False)
    expected = {'exposure_ns': exposure_ns, 'iso': iso, 'ae_mode': 'OFF', 'af_mode': 'OFF',
                'crop': list(crop), 'eis_mode': 'OFF', 'ois_mode': 'OFF'}
    for name, metadata in (('request', request), ('result', result)):
        for key, value in expected.items():
            _need(metadata[key] == value, f'Unexpected {name} {key}')
        _need(abs(metadata['focus_diopters'] - focus_diopters) < .001, f'Unexpected {name} focus')
        _need(abs(metadata['zoom'] - zoom) < 1e-6, f'Unexpected {name} zoom')
        _need(metadata['frame_duration_ns'] > 0 and
              abs(1e9 / metadata['frame_duration_ns'] / expected_fps - 1) < .03,
              f'Unexpected {name} frame duration')
    _need(request['request_id'] == result['request_id'], 'Request/result not settled to same request')
    _need(request['capture_intent'] == result['capture_intent'], 'Request/result capture-intent mismatch')
    _need(result['frame_count'] >= 0 and result['timestamp_ns'] > 0, 'Missing result progress')
    _need(0 < result['rolling_shutter_skew_ns'] <= result['frame_duration_ns'], 'Invalid rolling-shutter skew')
    streams = _streams(device, request_ids)
    encoder = [stream for stream in streams if stream['requested'] and
               stream['consumer_kind'] in ENCODER_CONSUMERS and
               (expected_size is None or (stream['width'], stream['height']) == tuple(expected_size))]
    recording = (request['capture_intent'] == 'VIDEO_RECORD' and len(encoder) == 1 and
                 encoder[0]['state'] == 4 and encoder[0]['frames_produced'] > 0 and
                 encoder[0]['last_timestamp_ns'] > 0)
    if require_recording:
        _need(recording, 'No qualified active recording stream')
    elif expected_size is not None:
        _need(any(stream['requested'] and (stream['width'], stream['height']) == tuple(expected_size)
                  for stream in streams), 'Expected output dimensions absent from last request')
    # An opaque continuity token avoids publishing process/address-bearing dump text.
    session_token = hashlib.sha256(f'{camera_id}|{client_pid}|{client_address}'.encode()).hexdigest()
    snapshot = {'camera_id': camera_id, 'client_package': package, 'session_token': session_token,
                'request': request, 'result': result, 'streams': streams,
                'recording_verified': recording,
                'encoder_stream_id': encoder[0]['id'] if recording else None,
                'frame_count': result['frame_count'], 'timestamp_ns': result['timestamp_ns'],
                'frame_duration_ns': result['frame_duration_ns'],
                'rolling_shutter_skew_ns': result['rolling_shutter_skew_ns'],
                'progress_verified': previous is not None,
                'interpretation': 'Settings and stream snapshots only; not per-frame video metadata or optical Hz.'}
    if previous is not None:
        _need(previous.get('session_token') == session_token, 'Camera client session changed')
        old = previous.get('result', {})
        for key in ('crop', 'zoom', 'focus_diopters', 'eis_mode', 'ois_mode',
                    'capture_intent', 'rolling_shutter_skew_ns'):
            _need(old.get(key) == result[key], f'Camera geometry or mode changed: {key}')
        _need(result['frame_count'] > old.get('frame_count', result['frame_count']), 'Camera frame count did not advance')
        _need(result['timestamp_ns'] > old.get('timestamp_ns', result['timestamp_ns']), 'Sensor timestamp did not advance')
        old_streams = {stream['id']: stream for stream in previous.get('streams', [])}
        _need(set(old_streams) == {stream['id'] for stream in streams}, 'Stream configuration changed')
        for stream in streams:
            before = old_streams[stream['id']]
            for key in ('width', 'height', 'pixel_format', 'consumer_kind', 'requested'):
                _need(before.get(key) == stream[key], f'Stream configuration changed: {key}')
            if stream['id'] == snapshot['encoder_stream_id']:
                _need(stream['frames_produced'] > before.get('frames_produced', stream['frames_produced']) and
                      stream['last_timestamp_ns'] > before.get('last_timestamp_ns', stream['last_timestamp_ns']),
                      'Encoder stream did not advance')
    return snapshot


def validate_shutter_setting(text: str, previous: dict[str, Any] | None = None,
                             **profile: Any) -> dict[str, Any]:
    """Inspect an unknown shutter value while calibrating a bounded UI search.

    Same strict checks as validate_capture, but derive expected exposure from the
    scoped latest result; the last request must agree. Return actual ns in
    snapshot['result']['exposure_ns']. The caller still checks target tolerance,
    repeatability, available signal, and settling on TWO advancing snapshots.
    This helper performs no gestures and must not replace an exact trial gate.
    """
    _need('exposure_ns' not in profile, 'Use validate_capture for a known exposure')
    scope, _ = _selected_scope(text, profile.get('camera_id', '0'))
    result_part = _between(scope, '    Latest received frame:\n', '  Device dump:\n', 'result')
    actual = _metadata(result_part, result=True)['exposure_ns']
    return validate_capture(text, previous, exposure_ns=actual, **profile)
