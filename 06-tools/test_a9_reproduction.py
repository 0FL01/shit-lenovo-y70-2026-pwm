"""Offline synthetic fixtures only. Never connect to a device or launch adb."""
import hashlib
import json
import re
from pathlib import Path
import struct
import subprocess
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
                with self.assertRaisesRegex(ValueError, 'C1 capture scope'):
                    a9.prepare(root, argv + ['--capture-c1'])
                c1_auth = dict(auth, c1_capture=a9.C1_SCOPE)
                source.write_text(json.dumps(c1_auth))
                self.assertEqual(a9.prepare(root, argv + ['--capture-c1'])[-1]['c1_capture'], a9.C1_SCOPE)
                with self.assertRaisesRegex(ValueError, 'without --capture-c1'):
                    a9.prepare(root, argv)
                for field, bad in [('length', 2), ('read_only', 1), ('refresh_hz', 90)]:
                    source.write_text(json.dumps(dict(auth, c1_capture=dict(a9.C1_SCOPE, **{field: bad}))))
                    with self.subTest(c1_field=field), self.assertRaises(ValueError):
                        a9.prepare(root, argv + ['--capture-c1'])
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

    def test_c1_main_trace_accounting_rejects_missing_extra_or_queued_callbacks(self):
        entry = 'mode_entry: pending=0 length=11 flags=0\nmode_return: rc=0\n'
        before = entry + 'mode_ctrl_return: rc=0\n'
        delta = entry * 3 + ''.join('mode_ctrl_return: rc=' + str(rc) + '\n' for rc in (0, 3, 0, 0))
        result = a9.validate_c1_trace(before, before + delta, 1)
        self.assertEqual(result['entry_count_after'], 4)
        self.assertEqual(result['controller_returns'], [0, 3, 0, 0])
        for bad in (delta + entry, delta.replace('pending=0', 'pending=11', 1),
                    delta.replace('length=11', 'length=12', 1), delta.replace('flags=0', 'flags=64', 1),
                    delta.replace('rc=3', 'rc=0'), delta.replace('rc=0', 'rc=-1', 1), delta + 'LOST'):
            with self.subTest(delta=bad), self.assertRaises(ValueError):
                a9.validate_c1_trace(before, before + bad, 1)
        with self.assertRaises(ValueError):
            a9.validate_c1_trace(before, before + delta, 0)
        with self.assertRaises(ValueError):
            a9.validate_c1_trace(before, (before + delta).replace('length=11', 'length=12', 1), 1)

    def test_c1_allows_only_known_background_esd_outside_callback_window(self):
        def line(time, event, data, task='printf'):
            return f' {task}-100 [001] d.... {time:.6f}: {event}: {data}\n'
        entry = 'pending=0 length=11 flags=0'
        before = line(1, 'mode_entry', entry) + line(1.1, 'mode_ctrl_return', 'rc=0') + line(1.2, 'mode_return', 'rc=0')
        delta = ''
        for t in (2, 3, 4):
            delta += line(t, 'mode_entry', entry) + line(t+.1, 'mode_ctrl_return', 'rc=0') + line(t+.2, 'mode_return', 'rc=0')
            if t == 2:
                delta += line(2.3, 'mode_ctrl_return', 'rc=3')
        call = '(dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1'
        esd = line(5, 'mode_ctrl_return', call, 'kworker/0:1')
        result = a9.validate_c1_trace(before, before + delta + esd, 1)
        self.assertEqual(result['controller_returns'], [0, 3, 0, 0])
        self.assertEqual(result['background_esd'][0]['kind'], 'native_esd_resumed_after_restoration')
        prior_esd = line(1.5, 'mode_ctrl_return', call, 'kworker/0:1')
        self.assertEqual(a9.validate_c1_trace(before, before + prior_esd + delta, 1)['background_esd'][0]['kind'], 'native_esd_before_c1_window')
        for bad in (esd.replace('kworker/0:1', 'printf'), esd.replace('+0x154/', '+0x158/'),
                    esd.replace('rc=1', 'rc=2'), esd.replace('rc=1', 'rc=-1'),
                    esd.replace('rc=1', 'rc=0'), esd.replace('validate_status', 'cmd_receive')):
            with self.subTest(extra=bad), self.assertRaises(ValueError):
                a9.validate_c1_trace(before, before + delta + bad, 1)
        middle = line(2.4, 'mode_ctrl_return', call, 'kworker/0:1')
        split = delta.index(' 3.000000:')
        index = delta.rfind('\n', 0, split) + 1
        with self.assertRaises(ValueError):
            a9.validate_c1_trace(before, before + delta[:index] + middle + delta[index:], 1)
        with self.assertRaises(ValueError):
            a9.validate_c1_trace(before, before.replace('1.100000', '1.110000') + delta + esd, 1)

    def test_saved_trial02_trace_and_background_esd_mutations(self):
        private = Path.home() / '.cache/legion-y70-trials/a9_c1_a001_20261108_02'
        if not (private / 'baseline-c1-trace-before.txt').exists():
            self.skipTest('Private on-target trace evidence unavailable on this host')
        before = (private / 'baseline-c1-trace-before.txt').read_text()
        after = (private / 'baseline-c1-trace-after.txt').read_text()
        count = len(re.findall(r'\bmode_entry:', before))
        result = a9.validate_c1_trace(before, after, count)
        self.assertEqual(result['controller_returns'], [0, 3, 0, 0])
        self.assertEqual(len(result['background_esd']), 1)
        self.assertEqual(result['background_esd'][0]['kind'], 'native_esd_resumed_after_restoration')
        extra = after.splitlines()[-1]
        self.assertIn('dsi_display_validate_status', extra)
        for bad in (extra.replace('kworker/0:1', 'printf'), extra.replace('rc=1', 'rc=2'),
                    extra.replace('rc=1', 'rc=-1'), extra.replace('+0x154/', '+0x158/'),
                    extra.replace('1982.432464', '1981.950000')):
            with self.subTest(mutation=bad), self.assertRaises(ValueError):
                a9.validate_c1_trace(before, after.replace(extra, bad), count)

    def test_root_mutex_never_overwrites_or_releases_other_token(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'mutex'
            # Ordinary temporary files only. Simulate required UID0 reporting;
            # actual mode, file/symlink and ownership-token checks run unchanged.
            prefix = 'stat() { if [ "$2" = %u ]; then printf 0; else command stat "$@"; fi; }; '
            def run(token, operation, root_uid=True):
                command = a9.lock_commands(token)[operation].replace(a9.LOCK, str(lock))
                if not root_uid:
                    return subprocess.run(['sh', '-c', prefix.replace('printf 0', 'printf 1') + command], capture_output=True)
                return subprocess.run(['sh', '-c', prefix + command], capture_output=True)
            self.assertEqual(run('experiment_owned', 'acquire').returncode, 0)
            self.assertEqual((lock / 'owner').read_text(), 'experiment_owned')
            self.assertNotEqual(run('experiment_other', 'acquire').returncode, 0)
            self.assertNotEqual(run('experiment_other', 'release').returncode, 0)
            self.assertEqual((lock / 'owner').read_text(), 'experiment_owned')
            self.assertNotEqual(run('experiment_owned', 'release', root_uid=False).returncode, 0)
            (lock / 'owner').chmod(0o644)
            self.assertNotEqual(run('experiment_owned', 'release').returncode, 0)
            (lock / 'owner').chmod(0o600)
            self.assertEqual(run('experiment_owned', 'verify').returncode, 0)
            self.assertEqual(run('experiment_owned', 'release').returncode, 0)
            self.assertFalse(lock.exists())
        for token in ('short', 'token; rm', '../invalid/token'):
            with self.assertRaises(ValueError):
                a9.lock_commands(token)

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
