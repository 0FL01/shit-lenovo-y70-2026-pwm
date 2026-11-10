import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import deploy_readonly as d
from test_probe import FakeTransport, Parser, Sink
import test_probe
import probe

class WrapperTests(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as parent:
            base = Path(parent)
            code = base / d.CODE; code.mkdir(mode=0o700)
            with patch.multiple(d, BASE=str(base), BASE_PIN=d.metadata(base.stat()),
                                CODE_PIN=d.metadata(code.stat()), HOST_UID=os.getuid()):
                config = test_probe.LauncherTests().fixture(base)
                config.pop('evidence')
                config['source_commit'] = d.COMMIT
                config['source_sha256'] = dict(d.SOURCE_HASHES)
                payload = {'base_path': str(base), 'base_pin': dict(d.BASE_PIN), 'code_name': d.CODE,
                    'code_pin': dict(d.CODE_PIN), 'config_without_evidence': config,
                    'probe_directory_name': d.DEST,
                    'files': {name: {'sha256': digest,
                        'utf8': Path(__file__).with_name(name).read_text()}
                        for name, digest in d.FILE_HASHES.items()}}
                yield base, payload

    def good_runner(self, calls, readonly=None):
        def run(args, **kwargs):
            calls.append((args, kwargs))
            if args[-1] == '--execute-read-only':
                result = readonly
            else:
                result = {'status': 'source_and_config_checked', 'device_services_sent': 0,
                          'setup_admitted': False, 'acquisition_qualified': False}
            return subprocess.CompletedProcess(args, 0, json.dumps(result).encode())
        return run

    def observation(self):
        return probe.Observation(FakeTransport(), (b'target-private', b'camera-private'),
                                 Parser, Sink(), lambda: 0).run()

    def test_default_source_only_and_private_exclusive_files(self):
        with self.fixture() as (base, payload):
            calls = []
            runner = d.Deployment(runner=self.good_runner(calls))
            result = runner.run(json.dumps(payload).encode())
            self.assertEqual(result['outcome'], 'source_only_validated')
            self.assertFalse(result['read_only_started'])
            self.assertTrue(result['host_cleanup_verified'])
            self.assertEqual(len(calls), 1)
            self.assertNotIn('--execute-read-only', calls[0][0])
            self.assertEqual(calls[0][0][:3], ['/usr/bin/python3', '-I', '-B'])
            directory = base / d.DEST
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            for name in ('launch.py', 'probe.py', 'config.json', 'begin.json', 'outcome.json'):
                self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), 0o600)
            stored = json.loads((directory / 'config.json').read_text())
            self.assertEqual(stored['evidence']['inode'], (directory / 'evidence').stat().st_ino)
            self.assertNotIn('target-private', json.dumps(result))
            self.assertNotIn('camera-private', json.dumps(result))
            self.assertNotIn('source_sha256', json.dumps(result))
            self.assertTrue(result['begin_utc'].endswith('+00:00'))
            with self.assertRaises(ValueError):
                runner.run(json.dumps(payload).encode())

    def test_readonly_after_sourceonly_exactly_once(self):
        with self.fixture() as (base, payload):
            calls = []
            result = d.Deployment(runner=self.good_runner(calls, self.observation())).run(
                json.dumps(payload).encode(), execute_read_only=True)
            self.assertEqual(result['outcome'], 'read_only_observed')
            self.assertTrue(result['source_only_validated'])
            self.assertEqual(len(calls), 2)
            self.assertNotIn('--execute-read-only', calls[0][0])
            self.assertEqual(calls[1][0][-1], '--execute-read-only')
            self.assertFalse(result['acquisition_qualified'])
            self.assertIsNotNone(result['read_only_begin_utc'])
            self.assertIsNotNone(result['read_only_end_utc'])
            self.assertIsNone(result['observation']['pwm_hz'])

    def test_collision_fail_without_subprocess_or_overwrite(self):
        with self.fixture() as (base, payload):
            directory = base / d.DEST; directory.mkdir(mode=0o700)
            sentinel = directory / 'keep'; sentinel.write_text('keep')
            calls = []
            result = d.Deployment(runner=self.good_runner(calls)).run(json.dumps(payload).encode())
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(calls, [])
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(directory.iterdir()), [sentinel])

    def test_wrong_pin_or_sources_before_mkdir(self):
        with self.fixture() as (base, original):
            for mutate in (lambda p: p['base_pin'].update(inode=1),
                           lambda p: p['files']['probe.py'].update(utf8='malicious'),
                           lambda p: p['files']['launch.py'].update(sha256='0' * 64),
                           lambda p: p.update(secret='blocked'),
                           lambda p: p['config_without_evidence'].update(password='blocked'),
                           lambda p: p['config_without_evidence'].update(source_commit='0' * 40)):
                payload = json.loads(json.dumps(original)); mutate(payload)
                calls = []
                result = d.Deployment(runner=self.good_runner(calls)).run(json.dumps(payload).encode())
                self.assertEqual(result['outcome'], 'failed')
                self.assertFalse((base / d.DEST).exists())
                self.assertEqual(calls, [])

    def test_real_base_or_frozen_code_mode_mismatch(self):
        with self.fixture() as (base, payload):
            (base / d.CODE).chmod(0o755)
            calls = []
            result = d.Deployment(runner=self.good_runner(calls)).run(json.dumps(payload).encode())
            self.assertEqual(result['outcome'], 'failed')
            self.assertFalse((base / d.DEST).exists())
            self.assertEqual(calls, [])

    def test_sourceonly_failure_does_not_run_observer(self):
        with self.fixture() as (base, payload):
            calls = []
            def fail(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args, 1, b'PRIVATE DO NOT ECHO')
            result = d.Deployment(runner=fail).run(json.dumps(payload).encode(), execute_read_only=True)
            self.assertEqual(result['outcome'], 'failed')
            self.assertFalse(result['read_only_started'])
            self.assertEqual(len(calls), 1)
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertTrue((base / d.DEST / 'config.json').exists())

    def test_readonly_failure_or_timeout_uncertain_no_retry(self):
        for timeout in (False, True):
            with self.fixture() as (base, payload):
                calls = []
                good = self.good_runner(calls)
                def runner(args, **kwargs):
                    if args[-1] == '--execute-read-only':
                        calls.append((args, kwargs))
                        if timeout:
                            raise subprocess.TimeoutExpired(args, 600, output=b'PRIVATE')
                        return subprocess.CompletedProcess(args, 1, b'PRIVATE')
                    return good(args, **kwargs)
                result = d.Deployment(runner=runner).run(json.dumps(payload).encode(), execute_read_only=True)
                self.assertEqual(result['outcome'], 'uncertain')
                self.assertEqual(len(calls), 2)
                self.assertNotIn('PRIVATE', json.dumps(result))

    def test_output_schema_blocks_identifier_leak(self):
        with self.fixture() as (base, payload):
            result = self.observation(); result['serial'] = 'PRIVATE'
            calls = []
            value = d.Deployment(runner=self.good_runner(calls, result)).run(
                json.dumps(payload).encode(), execute_read_only=True)
            self.assertEqual(value['outcome'], 'uncertain')
            self.assertIsNone(value['observation'])
            self.assertNotIn('PRIVATE', json.dumps(value))

    def test_oversize_duplicate_keys_and_no_device_surface(self):
        for raw in (b'x' * 65537, b'{"x":1,"x":2}'):
            with self.assertRaises(ValueError):
                d.parse_payload(raw)
        import ast
        tree = ast.parse(Path(d.__file__).read_text())
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls.intersection({'system', 'shell', 'reboot', 'chmod', 'unlink', 'rmdir', 'remove'}))

    def test_close_failure_disk_receipt_explicitly_provisional(self):
        class API:
            def __getattr__(self, name):
                return getattr(os, name)
            def open(self, path, *args, **kwargs):
                fd = os.open(path, *args, **kwargs)
                if path == d.BASE:
                    self.root_fd = fd
                return fd
            def close(self, fd):
                os.close(fd)
                if fd == getattr(self, 'root_fd', None):
                    raise OSError('private close detail')
        with self.fixture() as (base, payload):
            calls = []
            result = d.Deployment(api=API(), runner=self.good_runner(calls, self.observation())).run(
                json.dumps(payload).encode(), execute_read_only=True)
            self.assertEqual(result['outcome'], 'uncertain')
            self.assertEqual(result['stage'], 'close_failed')
            self.assertEqual(result['receipt_phase'], 'final')
            self.assertFalse(result['host_cleanup_verified'])
            stored = json.loads((base / d.DEST / 'outcome.json').read_text())
            self.assertEqual(stored['receipt_phase'], 'before_descriptor_close')
            self.assertFalse(stored['host_cleanup_verified'])
            self.assertNotIn('private close detail', json.dumps(result))

    def test_short_write_rejection_retains_partial_file_no_child(self):
        class API:
            def __getattr__(self, name):
                return getattr(os, name)
            def write(self, fd, content):
                return 0
        with self.fixture() as (base, payload):
            calls = []
            result = d.Deployment(api=API(), runner=self.good_runner(calls)).run(json.dumps(payload).encode())
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(calls, [])
            self.assertTrue((base / d.DEST / 'launch.py').exists())
            self.assertEqual((base / d.DEST / 'launch.py').stat().st_size, 0)

if __name__ == '__main__':
    unittest.main()
