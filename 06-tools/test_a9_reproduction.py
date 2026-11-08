"""Offline synthetic fixtures only. Never connect to a device or launch adb."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

import a9_reproduction as a9
from guarded_adb_socket import GuardedADB

ROOT = Path(__file__).resolve().parents[1]


class FakeSocket:
    def __init__(self, data):
        self.data = bytearray(data)
        self.sent = bytearray()
    def recv(self, count):
        data = self.data[:min(count, 2)]  # Deliberate short reads.
        del self.data[:len(data)]
        return bytes(data)
    def sendall(self, data): self.sent.extend(data)
    def settimeout(self, value): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


class ReproductionTests(unittest.TestCase):
    def test_exact_a9_native_byte_only(self):
        data = a9.programs(ROOT)
        self.assertEqual([i for i, (x, y) in enumerate(zip(data['stock'], data['a9_only'])) if x != y], [68])
        self.assertEqual((data['stock'][68], data['a9_only'][68]), (14, 142))
        self.assertEqual(data['a9_only'][97], 14)

    def test_redraw_rejects_native_writes_and_incomplete_evidence(self):
        begin, end = 'PWM_A9_REDRAW_BEGIN_a9_only', 'PWM_A9_REDRAW_END_a9_only'
        clean = begin + '\nframe-only unrelated kernel log\n' + end
        self.assertEqual(a9.verify_redraw_interval(clean, 'PWM_A9', 'a9_only')['native_dsi_writes'], 0)
        for bad in (begin, end + begin, clean + begin,
                    begin + '\ndsi-ctrl-1: dsi_ctrl_cmd_transfer len=3 type=0x39\n' + end,
                    begin + '\nCommand transfer failed\n' + end):
            with self.subTest(log=bad), self.assertRaises(ValueError):
                a9.verify_redraw_interval(bad, 'PWM_A9', 'a9_only')

    def test_fresh_authorization_bound_to_output_and_dbv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / 'artifacts/device_tree/selected_boe_v4'
            panel.mkdir(parents=True)
            for name in ('qcom,mdss-dsi-dc-off-command', 'qcom,mdss-dsi-dc-on-command'):
                (panel / name).write_bytes((ROOT / 'artifacts/device_tree/selected_boe_v4' / name).read_bytes())
            auth = dict(experiment_id='synthetic_test_only', mode='a9_reproduction',
                        sequence=['stock', 'a9_only', 'stock'], candidates=['a9_only'],
                        program_sha256={k: hashlib.sha256(v).hexdigest() for k, v in a9.programs(root).items()},
                        native_dbv=828, output='artifacts/new_test', emergency_reboot_approved=True,
                        watchdog_reboot_approved=True, watchdog_seconds=600,
                        camera_profile='A001_Galaga_OpenCamera_1.56.2_720p_h264_no_audio_100us_iso6400',
                        owner_confirmation='SYNTHETIC OFFLINE TEST ONLY', approved_at_utc=datetime.now(timezone.utc).isoformat())
            source = root / 'fixture.json'
            argv = ['1', '2', '--experiment-id', auth['experiment_id'], '--authorization', str(source),
                    '--output', str(root / auth['output']), '--dbv', '828', '--offline-check']
            with patch('pathlib.Path.home', return_value=root), patch('subprocess.run', side_effect=AssertionError('No processes')):
                source.write_text(json.dumps(auth))
                _, out, private, data, scope = a9.prepare(root, argv)
                self.assertFalse(out.exists())
                self.assertFalse(private.exists())
                self.assertNotIn('owner_confirmation', scope)
                for key, bad in [('experiment_id', 'old_trial'), ('native_dbv', 3600), ('output', 'artifacts/old'),
                                 ('sequence', ['stock', 'a9_only']), ('watchdog_reboot_approved', False),
                                 ('program_sha256', {}), ('owner_confirmation', '')]:
                    invalid = dict(auth, **{key: bad})
                    source.write_text(json.dumps(invalid))
                    with self.subTest(key=key), self.assertRaises(ValueError):
                        a9.prepare(root, argv)
                source.write_text(json.dumps(auth))
                out.mkdir()
                with self.assertRaisesRegex(ValueError, 'one-shot'):
                    a9.prepare(root, argv)

    def test_socket_mandatory_and_no_default_or_retry(self):
        for spec in ('', 'tcp:localhost:5037', 'localfilesystem:relative'):
            with patch.dict('os.environ', {}, clear=True), self.assertRaises(ValueError):
                GuardedADB(spec)
        guard = GuardedADB('localfilesystem:/nonexistent-synthetic-test-socket')
        with patch('subprocess.run', side_effect=AssertionError('Never spawn adb')):
            with self.assertRaises(FileNotFoundError): guard.host('host:version')
            with self.assertRaises(ValueError): guard.run(['adb', 'devices', '-l'])
            with self.assertRaises(RuntimeError): guard.selected(1, 'shell,v2,raw:id', 2)

    def test_fragmented_protocol_and_shell_exit(self):
        guard = GuardedADB('localfilesystem:/synthetic')
        frame = lambda channel, payload: struct.pack('<BI', channel, len(payload)) + payload
        sock = FakeSocket(frame(1, b'hello') + frame(2, b'warning') + frame(3, b'\x07'))
        with patch.object(guard, 'selected', return_value=sock):
            result = guard.run(['adb', '-t', '1', 'shell', 'id'], text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, 'hello', 'warning'))
        with self.assertRaisesRegex(RuntimeError, 'outcome may be uncertain'):
            guard.exact(FakeSocket(b'a'), 2)
        with self.assertRaisesRegex(RuntimeError, 'refused'):
            guard.request(FakeSocket(b'FAIL'), 'host:version')

    def test_bound_serial_survives_id_reuse_and_reboot(self):
        guard = GuardedADB('localfilesystem:/synthetic')
        guard.identities = {'1': b'SYNTHETIC_TARGET', '2': b'SYNTHETIC_CAMERA'}
        with patch.object(guard, 'host', side_effect=AssertionError('Do not reinterpret alias')):
            self.assertEqual(guard.run(['adb', '-t', '1', 'get-serialno']).stdout, b'SYNTHETIC_TARGET')
        guard.protocol = b'0029'
        sock = FakeSocket(b'OKAYOKAY')
        with patch.object(guard, 'host', return_value=b'0029'), patch.object(guard, 'connect', return_value=sock):
            guard.selected(1, 'shell,v2,raw:id', 2)
        self.assertIn(b'host:transport:SYNTHETIC_TARGET', sock.sent)
        with patch.object(guard, 'host', return_value=b'SYNTHETIC_TARGET device device:avr transport_id:2\n'):
            self.assertEqual(guard.wait_target('SYNTHETIC_TARGET', timeout=1), 2)
        self.assertEqual(guard.identities, {'1': b'SYNTHETIC_TARGET', '2': b'SYNTHETIC_CAMERA'})

    def test_sync_pull_exclusive_and_push_ack(self):
        guard = GuardedADB('localfilesystem:/synthetic')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'
            sock = FakeSocket(struct.pack('<4sI', b'DATA', 3) + b'abc' + struct.pack('<4sI', b'DONE', 0))
            with patch.object(guard, 'selected', return_value=sock):
                guard.sync(1, path, '/sdcard/test.mp4', pull=True, timeout=2)
            self.assertEqual(path.read_bytes(), b'abc')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.object(guard, 'selected', return_value=FakeSocket(b'')), self.assertRaises(FileExistsError):
                guard.sync(1, path, '/sdcard/test.mp4', pull=True, timeout=2)
            sock = FakeSocket(struct.pack('<4sI', b'OKAY', 0))
            with patch.object(guard, 'selected', return_value=sock):
                guard.sync(1, path, '/data/local/tmp/chunk', pull=False, timeout=2)
            self.assertIn(b'DATA\x03\x00\x00\x00abc', sock.sent)
            self.assertIn(b',33216', sock.sent)


if __name__ == '__main__':
    unittest.main()
