"""Offline synthetic guards for camera snapshot qualification; no device access."""
from __future__ import annotations

import unittest

from camera_capture_metadata import (CaptureMetadataError, FIELDS, RESULT_ONLY,
                                     validate_capture, validate_shutter_setting)


def sample(*, frame=100, timestamp=10000000000, recording=True, exposure=100000,
           iso=6400, session='synthetic-session', encoder_frames=90):
    values = {'exposure_ns': exposure, 'iso': iso, 'ae_mode': 'OFF', 'af_mode': 'OFF',
              'focus_diopters': 2.03874850, 'crop': [0, 0, 4080, 3072], 'zoom': 1.0,
              'eis_mode': 'OFF', 'ois_mode': 'OFF',
              'capture_intent': 'VIDEO_RECORD' if recording else 'PREVIEW',
              'request_id': 3, 'frame_duration_ns': 33350000, 'frame_count': frame,
              'timestamp_ns': timestamp, 'rolling_shutter_skew_ns': 15047630}

    def metadata(result):
        lines = ['      Dumping camera metadata array: synthetic fixture\n']
        for key, (tag, converter, count) in FIELDS.items():
            if not result and key in RESULT_ONLY:
                continue
            value = values[key]
            if not result and key == 'frame_duration_ns':
                value = 33333333
            tokens = value if isinstance(value, list) else [value]
            datatype = 'float' if converter is float else 'byte' if converter is str else 'int64'
            lines.append(f'        {tag} (00001): {datatype}[{count}]\n')
            lines.append('          [' + ' '.join(str(v) for v in tokens) + ' ]\n')
        return ''.join(lines)

    def stream(stream_id, consumer, width, height, produced):
        return (f'    Stream[{stream_id}]: Output\n      Consumer name: {consumer}\n'
                f'      State: 4\n      Dims: {width} x {height}, format 0x1000, dataspace 0x10c10000\n'
                f'      Frames produced: {produced}, last timestamp: {timestamp} ns\n')

    streams = stream(2, 'SurfaceTexture-synthetic', 1920, 1080, encoder_frames)
    if recording:
        streams += stream(3, 'GraphicBufferSource', 1280, 720, encoder_frames)
    return ('Active Camera Clients:\n'
            '(Camera ID: 0, Cost: 100, Client Package Name: net.sourceforge.opencamera, Conflicting Client Devices: {})\n'
            '== Camera device 0 dynamic info: ==\n'
            '    Client PID: 42\n    Client package: net.sourceforge.opencamera\n'
            f'  CameraDeviceClient[0] ({session}) dump:\n'
            '    Latest received frame:\n' + metadata(True) +
            '  Device dump:\n    Device status: ACTIVE\n    Stream configuration:\n' + streams +
            '    Camera3 Buffer Manager:\n    Last request sent:\n      Output Stream Ids:\n         2\n' +
            ('         3\n' if recording else '') + '    Logical request settings:\n' + metadata(False) +
            '     Tag monitoring disabled\n     HAL device dump:\n'
            '== Camera device 1 dynamic info: ==\n  Device 1 is closed, no client instance\n')


class CameraCaptureMetadataTests(unittest.TestCase):
    def test_recording_valid_and_private_tokens_not_copied(self):
        result = validate_capture(sample(), require_recording=True)
        self.assertTrue(result['recording_verified'])
        self.assertFalse(result['progress_verified'])
        self.assertEqual(result['result']['exposure_ns'], 100000)
        self.assertNotIn('synthetic-session', str(result))
        self.assertNotIn('SurfaceTexture-synthetic', str(result))

    def test_preview_allowed_but_not_recording(self):
        text = sample(recording=False)
        self.assertFalse(validate_capture(text)['recording_verified'])
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text, require_recording=True)

    def test_advancing_recording(self):
        previous = validate_capture(sample(), require_recording=True)
        result = validate_capture(sample(frame=160, timestamp=12000000000, encoder_frames=150),
                                  previous, require_recording=True)
        self.assertTrue(result['progress_verified'])

    def test_repeated_snapshot_rejected(self):
        previous = validate_capture(sample())
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample(), previous)

    def test_timestamp_must_advance_independently_of_frame_count(self):
        previous = validate_capture(sample())
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample(frame=160, encoder_frames=150), previous)

    def test_encoder_must_advance_independently_of_result(self):
        previous = validate_capture(sample(), require_recording=True)
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample(frame=160, timestamp=12000000000), previous, require_recording=True)

    def test_other_client_and_static_metadata_cannot_supply_missing_result(self):
        text = sample()
        tag = '        android.sensor.exposureTime (00001): int64[1]\n          [100000 ]\n'
        text = text.replace(tag, '', 1) + '\nStatic metadata:\n' + tag
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text)

    def test_duplicate_result_tag_rejected(self):
        text = sample()
        tag = '        android.sensor.exposureTime (00001): int64[1]\n          [100000 ]\n'
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text.replace(tag, tag + tag, 1))

    def test_missing_result_section_rejected(self):
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample().replace('Latest received frame:', 'Cached received frame:'))

    def test_duplicate_selected_camera_rejected(self):
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample() + sample())

    def test_changed_session_rejected(self):
        previous = validate_capture(sample())
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample(frame=160, timestamp=12000000000, encoder_frames=150,
                                    session='different-session'), previous)

    def test_active_client_mismatch_rejected(self):
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample().replace('Client Package Name: net.sourceforge.opencamera',
                                              'Client Package Name: other.app'))

    def test_request_result_mismatch_rejected(self):
        text = sample().replace('[100000 ]', '[500000 ]', 1)
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text)

    def test_expected_shutter_and_iso_can_be_changed_explicitly(self):
        previous = validate_capture(sample())
        text = sample(frame=160, timestamp=12000000000, encoder_frames=150, exposure=500000, iso=1600)
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text, previous)
        result = validate_capture(text, previous, exposure_ns=500000, iso=1600)
        self.assertEqual(result['result']['exposure_ns'], 500000)

    def test_skew_and_stream_layout_must_stay_stable(self):
        previous = validate_capture(sample())
        second = sample(frame=160, timestamp=12000000000, encoder_frames=150)
        for changed in (second.replace('[15047630 ]', '[15596307 ]'),
                        second.replace('Dims: 1280 x 720', 'Dims: 1920 x 1080')):
            with self.subTest(changed=changed[-40:]):
                with self.assertRaises(CaptureMetadataError):
                    validate_capture(changed, previous)

    def test_dimensions_and_encoder_evidence_required(self):
        for changed in (sample().replace('Dims: 1280 x 720', 'Dims: 1920 x 1080'),
                        sample().replace('GraphicBufferSource', 'UnknownConsumer'),
                        sample(encoder_frames=0),
                        sample().replace('[VIDEO_RECORD ]', '[PREVIEW ]')):
            with self.assertRaises(CaptureMetadataError):
                validate_capture(changed, require_recording=True)

    def test_unsettled_request_id_rejected(self):
        text = sample().replace('android.request.id (00001): int64[1]\n          [3 ]',
                                'android.request.id (00001): int64[1]\n          [2 ]', 1)
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text)

    def test_unsupported_physical_metadata_rejected(self):
        text = sample().replace('     HAL device dump:', '    Physical request settings:\n     HAL device dump:')
        with self.assertRaises(CaptureMetadataError):
            validate_capture(text)

    def test_invalid_expected_profile_rejected(self):
        for options in ({'exposure_ns': 0}, {'iso': -1}, {'expected_fps': float('nan')},
                        {'crop': (1, 2)}, {'expected_size': (0, 720)}, {'zoom': float('inf')}):
            with self.assertRaises(CaptureMetadataError):
                validate_capture(sample(), **options)


    def test_shutter_calibration_reads_actual_scoped_exposure(self):
        result = validate_shutter_setting(sample(exposure=625000), require_recording=True)
        self.assertEqual(result['result']['exposure_ns'], 625000)
        with self.assertRaises(CaptureMetadataError):
            validate_capture(sample(exposure=625000))

    def test_shutter_calibration_does_not_relax_other_settings_or_settling(self):
        for text in (sample(iso=1600), sample(exposure=0),
                     sample(exposure=625000).replace('[625000 ]', '[100000 ]', 1)):
            with self.assertRaises(CaptureMetadataError):
                validate_shutter_setting(text)
        with self.assertRaises(CaptureMetadataError):
            validate_shutter_setting(sample(), exposure_ns=100000)


if __name__ == '__main__':
    unittest.main()
