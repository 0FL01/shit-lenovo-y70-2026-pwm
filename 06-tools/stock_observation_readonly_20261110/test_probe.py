import ast
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch

import probe as p
import launch

BOOT = '12345678-1234-1234-1234-123456789abc'

class Parser:
    class CaptureMetadataError(ValueError):
        pass
    ENCODER_CONSUMERS = {'MediaRecorder', 'GraphicBufferSource', 'CameraSource'}
    @staticmethod
    def _selected_scope(text, camera_id):
        if text == 'bad':
            raise Parser.CaptureMetadataError('private-token-never-visible')
        return text, ''
    @staticmethod
    def _between(*args):
        return ''
    @staticmethod
    def _metadata(*args, **kwargs):
        return {'exposure_ns': 100000, 'iso': 6400, 'focus_diopters': 2.0387485,
                'crop': [0, 0, 4080, 3072], 'zoom': 1.0, 'frame_duration_ns': 33333333}
    @staticmethod
    def validate_capture(text, **kwargs):
        if text == 'bad':
            raise Parser.CaptureMetadataError('private-token-never-visible')
        return {'recording_verified': False, 'request': {'capture_intent': 'PREVIEW'},
            'result': {'capture_intent': 'PREVIEW', 'exposure_ns': 100000, 'iso': 6400,
                'focus_diopters': 2.0387485, 'zoom': 1.0, 'frame_duration_ns': 33333333},
            'streams': [], 'session_token': 'private-token-never-visible'}

class Sink:
    def validate(self):
        pass
    def write(self, value):
        self.value = value

class FakeTransport:
    def __init__(self):
        self.calls = []
        self.responses = {
            'boot': BOOT, 'target_identity': '\n'.join(p.TARGET),
            'camera_identity': '\n'.join(p.CAMERA), 'root': '0', 'panel': p.PANEL,
            'module': p.MODULE + '  /vendor/lib/modules/msm_drm.ko',
            'settings': '98\n0\n120.0\n120.0\n1800000',
            'native': '6438\n0\n0\nlogger: 0', 'mutex': 'absent',
            'power': '  mWakefulness=Awake', 'window': 'mShowingLockscreen=false',
            'foreground': 'mResumedActivity: ActivityRecord{private unrelated.package/.Secret}',
            'package': '  versionCode=90 minSdk=21\n  versionName=1.56.2', 'metadata': 'private raw dump',
        }
    def preflight(self):
        self.calls.append(('preflight',))
    def host(self, service):
        self.calls.append(('host', service))
        return b'target-private device transport_id:7\ncamera-private device transport_id:9\n'
    def bind(self, tid):
        self.calls.append(('bind', tid))
        return {'7': b'target-private', '9': b'camera-private'}[tid]
    def shell(self, tid, command, timeout):
        self.calls.append(('shell', tid, command, timeout))
        operation = next(k for k, v in p.COMMANDS.items() if v == command)
        role = {'7': 'target', '9': 'camera'}[tid]
        if role not in p.ROLES[operation]:
            raise AssertionError('Wrong operation role')
        return 0, self.responses[operation].encode(), b''

class ProbeTests(unittest.TestCase):
    def make(self, transport=None, parser=Parser):
        transport, sink = transport or FakeTransport(), Sink()
        obs = p.Observation(transport, (b'target-private', b'camera-private'), parser, sink, lambda: 0)
        return obs, transport, sink

    def test_reads_and_private_boots(self):
        obs, transport, sink = self.make()
        result = obs.run()
        self.assertTrue(result['camera_stopped_preview_verified'])
        self.assertEqual(result['native_dbv'], 6438)
        self.assertEqual(result['camera_version_code'], 90)
        self.assertIsNone(result['camera_duration_seconds'])
        self.assertIsNone(result['camera_restart_count'])
        self.assertFalse(result['setup_admitted'])
        self.assertFalse(result['acquisition_qualified'])
        visible = json.dumps(result)
        for secret in ('target-private', 'camera-private', BOOT, 'private', 'session_token', 'transport_alias'):
            self.assertNotIn(secret, visible)
        self.assertEqual(sink.value['roles']['target']['boot_id_before'], BOOT)
        self.assertEqual(sink.value['roles']['camera']['boot_id_after'], BOOT)
        self.assertNotIn('private raw dump', json.dumps(sink.value))
        self.assertTrue(all(c[0] in ('preflight', 'host', 'bind', 'shell') for c in transport.calls))
        self.assertTrue(all(c[2] in p.COMMANDS.values() for c in transport.calls if c[0] == 'shell'))
        with self.assertRaises(p.Rejected):
            obs.run()

    def test_wrong_identity_or_root_or_state_fail_closed(self):
        for key, value in [('target_identity', 'wrong'), ('camera_identity', 'wrong'),
                           ('root', '2000'), ('module', 'wrong'), ('boot', 'wrong'),
                           ('settings', '98\n0\nNaN\n120\n10'), ('native', '6438\n0\n0\nunknown')]:
            with self.subTest(key=key):
                obs, t, sink = self.make()
                t.responses[key] = value
                with self.assertRaisesRegex(p.Rejected, '^read_only_probe_failed$'):
                    obs.run()
                self.assertFalse(hasattr(sink, 'value'))

    def test_reboot_during_probe_rejects(self):
        obs, t, sink = self.make()
        original = t.shell
        count = 0
        def shell(*args):
            nonlocal count
            if args[1] == p.COMMANDS['boot']:
                count += 1
                if count > 2:
                    return 0, b'87654321-1234-1234-1234-123456789abc', b''
            return original(*args)
        t.shell = shell
        with self.assertRaises(p.Rejected):
            obs.run()
        self.assertFalse(hasattr(sink, 'value'))

    def test_failure_stops_without_retry_or_cleanup(self):
        obs, t, sink = self.make()
        t.shell = lambda *a: (_ for _ in ()).throw(RuntimeError('PRIVATE_SERIAL'))
        with self.assertRaisesRegex(p.Rejected, '^read_only_probe_failed$') as ctx:
            obs.run()
        self.assertIsNone(ctx.exception.__cause__)
        self.assertFalse(hasattr(sink, 'value'))

    def test_metadata_unknown_and_package_untrusted_not_echoed(self):
        obs, t, sink = self.make()
        t.responses['metadata'] = 'bad'
        t.responses['package'] = 'versionName=secret-token\nversionCode=secret-token'
        result = obs.run()
        self.assertFalse(result['camera_stopped_preview_verified'])
        self.assertIsNone(result['camera_profile'])
        self.assertIsNone(result['camera_version_code'])
        self.assertIsNone(result['camera_version_name'])

    def test_recording_never_ready(self):
        class Recording(Parser):
            @staticmethod
            def validate_capture(text, **kwargs):
                value = Parser.validate_capture(text)
                value['streams'] = [{'consumer_kind': 'MediaRecorder'}]
                return value
        result = self.make(parser=Recording)[0].run()
        self.assertFalse(result['camera_stopped_preview_verified'])

    def test_wrong_inventory_and_binding_stop(self):
        for wrong in (b'', b'target-private offline transport_id:7\ncamera-private device transport_id:9',
                      b'target-private device transport_id:7\ncamera-private device transport_id:7'):
            obs, t, sink = self.make()
            t.host = lambda service: wrong
            with self.assertRaises(p.Rejected):
                obs.run()
            self.assertFalse(any(c[0] == 'shell' for c in t.calls))
        obs, t, _ = self.make()
        t.bind = lambda tid: b'wrong'
        with self.assertRaises(p.Rejected):
            obs.run()
        self.assertFalse(any(c[0] == 'shell' for c in t.calls))

    def test_fixed_surface(self):
        tree = ast.parse(Path(p.__file__).read_text())
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls.intersection({'setup', 'execute', 'restore', 'finalize', 'reboot', 'sync', 'system', 'Popen'}))
        for command in p.COMMANDS.values():
            for forbidden in ('settings put', 'input ', 'uiautomator', 'am start', 'am force-stop',
                              ' > ', '>>', 'reboot', 'mkdir', 'chmod', 'rm ', 'reg_write', 'reg_read'):
                self.assertNotIn(forbidden, command)
        self.assertNotIn('shell', p.Observation.__dict__)
        with self.assertRaises(TypeError):
            p.COMMANDS['bad'] = 'reboot'

class SinkTests(unittest.TestCase):
    def inputs(self, directory):
        meta = os.stat(directory)
        return p.PrivateInputs(None, None, (b'a', b'b'), os.getuid(), str(directory), meta.st_dev, meta.st_ino)

    def test_private_exclusive_size_and_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = self.inputs(directory)
            p.PrivateEvidence(cfg).write({'boot_id': BOOT})
            path = Path(directory, 'readiness.json')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text())['boot_id'], BOOT)
            with self.assertRaises(FileExistsError):
                p.PrivateEvidence(cfg).write({})
            with self.assertRaises(p.Rejected):
                p.PrivateEvidence(dataclasses.replace(cfg, evidence_inode=cfg.evidence_inode + 1)).write({})

    def test_symlink_and_world_readable_refused(self):
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent, 'target'); target.mkdir(mode=0o700)
            link = Path(parent, 'link'); link.symlink_to(target)
            cfg = self.inputs(link)
            with self.assertRaises(OSError):
                p.PrivateEvidence(cfg).write({})
            self.assertFalse(Path(target, 'readiness.json').exists())
            target.chmod(0o755)
            with self.assertRaises(p.Rejected):
                p.PrivateEvidence(self.inputs(target)).write({})

    def test_oversize_one_shot(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = p.PrivateEvidence(self.inputs(directory))
            with self.assertRaises(p.Rejected):
                sink.write({'x': 'a' * 65536})
            with self.assertRaises(p.Rejected):
                sink.write({})
            self.assertFalse(Path(directory, 'readiness.json').exists())

class LoaderTests(unittest.TestCase):
    def test_reject_wrong_digest_before_execute(self):
        with patch.dict(sys.modules):
            for name in p.SOURCES:
                sys.modules.pop(name, None)
            raw = {name: b'raise RuntimeError("executed")' for name in p.SOURCES}
            with self.assertRaises(p.Rejected):
                p.load_sources(raw, {name: '0' * 64 for name in p.SOURCES})
            self.assertFalse(set(p.SOURCES).intersection(sys.modules))

    def test_exact_sources_load_inert_and_reject_preload(self):
        root = Path(__file__).resolve().parents[2]
        raw = {name: (root / path).read_bytes() for name, path in p.SOURCES.items()}
        pins = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
        # This derived pin is ONLY a fixture, never an operator approval.
        with patch.dict(sys.modules):
            for name in p.SOURCES:
                sys.modules.pop(name, None)
            with patch('socket.socket', side_effect=AssertionError('network forbidden')):
                modules = p.load_sources(raw, pins)
                self.assertEqual(set(modules), set(p.SOURCES))
            with self.assertRaises(p.Rejected):
                p.load_sources(raw, pins)

    def test_real_metadata_parser_preview_without_token_leak(self):
        root = Path(__file__).resolve().parents[2]
        raw = {name: (root / path).read_bytes() for name, path in p.SOURCES.items()}
        with patch.dict(sys.modules):
            for name in p.SOURCES:
                sys.modules.pop(name, None)
            modules = p.load_sources(raw, {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()})
            spec = importlib.util.spec_from_file_location('camera_fixture', root / '06-tools/test_camera_capture_metadata.py')
            fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
            obs, transport, sink = ProbeTests().make(parser=modules['camera_capture_metadata'])
            transport.responses['metadata'] = fixture.sample(recording=False)
            result = obs.run()
            self.assertTrue(result['camera_stopped_preview_verified'])
            self.assertNotIn('session_token', json.dumps(result))
            self.assertNotIn('synthetic-session', json.dumps(sink.value))

class LauncherTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(__file__).resolve().parents[2]
        import subprocess
        commit = subprocess.check_output(['/usr/bin/git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip()
        hashes = {k: hashlib.sha256((root / path).read_bytes()).hexdigest() for k, path in p.SOURCES.items()}
        hashes['probe'] = hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest()
        meta = os.stat(directory)
        return {'schema': 1, 'source_commit': commit, 'source_sha256': hashes,
            'process': {'pid': 1, 'starttime': 1, 'uids': [0, 0, 0, 0], 'executable': '/usr/bin/adb',
                'executable_device': 1, 'executable_inode': 1, 'executable_mode': stat.S_IFREG | 0o755,
                'executable_uid': 0, 'version': 'Android Debug Bridge version 1.0.41\nVersion synthetic-only\n'},
            'association': {'listener_inode': 1, 'network_namespace': 'net:[1]',
                'executable_sha256': '0' * 64, 'executable_size': 1},
            'limits': {k: 1024 for k in ('tcp_bytes', 'stat_bytes', 'status_bytes', 'max_pids',
                'max_fds_per_pid', 'max_total_fds', 'link_bytes')},
            'serials': ['target-private', 'camera-private'], 'host_uid': os.getuid(),
            'evidence': {'directory': str(directory), 'device': meta.st_dev, 'inode': meta.st_ino}}

    def test_config_rejects_extras_secrets_duplicates_booleans(self):
        with tempfile.TemporaryDirectory() as directory:
            base = self.fixture(directory)
            self.assertEqual(launch.parse_config(json.dumps(base))['schema'], 1)
            for key, value in [('password', 'secret'), ('schema', True), ('serials', ['same', 'same'])]:
                config = dict(base); config[key] = value
                with self.assertRaises(ValueError):
                    launch.parse_config(json.dumps(config))
            with self.assertRaises(ValueError):
                launch.parse_config('{"schema":1,"schema":1}')
            config = json.loads(json.dumps(base)); config['process']['pid'] = True
            with self.assertRaises(ValueError):
                launch.parse_config(json.dumps(config))

    def test_source_only_launcher_no_socket_proc_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules):
            for name in (*p.SOURCES, 'stock_readonly_probe'):
                sys.modules.pop(name, None)
            config = self.fixture(directory)
            path = Path(directory, 'config.json'); path.write_text(json.dumps(config)); path.chmod(0o600)
            output = io.StringIO()
            with patch('socket.socket', side_effect=AssertionError('forbidden network')), contextlib.redirect_stdout(output):
                rc = launch.main(['--source-root', str(Path(__file__).resolve().parents[2]),
                    '--probe-source', p.__file__, '--private-config', str(path)])
            self.assertEqual(rc, 0, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())['device_services_sent'], 0)
            self.assertNotIn('private', output.getvalue())
            self.assertFalse(Path(directory, 'readiness.json').exists())

    def test_config_permissions_and_wrong_source_pin_before_socket(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules):
            config = self.fixture(directory)
            path = Path(directory, 'config.json'); path.write_text(json.dumps(config)); path.chmod(0o644)
            with self.assertRaises(ValueError):
                launch.read_file(str(path), 16384, private=True)
            path.chmod(0o600)
            config['source_sha256']['probe'] = '0' * 64
            path.write_text(json.dumps(config))
            output = io.StringIO()
            with patch('socket.socket', side_effect=AssertionError('network forbidden')), contextlib.redirect_stdout(output):
                rc = launch.main(['--source-root', str(Path(__file__).resolve().parents[2]),
                    '--probe-source', p.__file__, '--private-config', str(path), '--execute-read-only'])
            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(output.getvalue())['status'], 'read_only_probe_failed')
            self.assertNotIn(str(path), output.getvalue())

    def test_failed_private_sink_validation_before_device(self):
        obs, transport, sink = ProbeTests().make()
        sink.validate = lambda: (_ for _ in ()).throw(ValueError('secret'))
        with self.assertRaises(p.Rejected):
            obs.run()
        self.assertEqual(transport.calls, [])

if __name__ == '__main__':
    unittest.main()
