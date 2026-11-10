import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

import prestart_inspection as i
import probe as base
import test_probe as fixtures

ROOT = Path(__file__).resolve().parents[2]

def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\0\0\0\0\xff')) + chunk(b'IEND', b'')

class MemorySink:
    def __init__(self):
        self.files = {}; self.opened = False; self.closed = False
    def open(self):
        if self.opened:
            raise ValueError('spent')
        self.opened = True
    def check(self):
        if not self.opened or self.closed:
            raise ValueError('not open')
    def write(self, name, raw):
        self.check()
        if name in self.files:
            raise ValueError('collision')
        self.files[name] = raw
        return {'device': 1, 'inode': len(self.files), 'size': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(), 'mode': stat.S_IFREG | 0o600, 'uid': 0}
    def close(self):
        self.closed = True

class InspectionTests(unittest.TestCase):
    def context(self):
        modules = base.load_sources({k: (ROOT / p).read_bytes() for k, p in base.SOURCES.items()},
            {k: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for k, p in base.SOURCES.items()})
        spec = importlib.util.spec_from_file_location('prestart_camera_fixture', ROOT / '06-tools/test_camera_capture_metadata.py')
        fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
        class Transport(fixtures.FakeTransport):
            def __init__(self):
                super().__init__(); self.frames = 0; self.extra_calls = []
                self.extra = {'native': '[1.0] dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000',
                    'software': 'mActiveSfDisplayMode= modeId=2 peakRefreshRate=120.0',
                    'activity': 'mResumedActivity: ActivityRecord{123 u0 com.android.settings/.Settings t3}',
                    'focus': 'mCurrentFocus=Window{123 u0 com.android.settings/com.android.settings.Settings}',
                    'lock': 'showing=false\ninputRestricted=false'}
            def shell(self, tid, command, timeout):
                if command == i.COMMANDS['metadata']:
                    self.frames += 1
                    return 0, fixture.sample(recording=False, frame=100 + self.frames,
                        timestamp=10000000000 + self.frames * 33350000).encode(), b''
                if command == i.COMMANDS['screenshot']:
                    self.extra_calls.append((tid, command, timeout))
                    return 0, png(), b''
                for op, value in self.extra.items():
                    if command == i.COMMANDS[op]:
                        self.extra_calls.append((tid, command, timeout))
                        return 0, value.encode(), b''
                return super().shell(tid, command, timeout)
        parsers = {n: i.extracted_parser((ROOT / p).read_bytes(), n, digest)
                   for n, (p, digest) in i.PARSER_SOURCES.items()}
        return dict(base=base, modules=modules, adapter=Transport(), serials=(b'target-private', b'camera-private'),
            config={'source_commit': i.COMMIT, 'source_sha256': {}}, parsers=parsers,
            sink=MemorySink(), provenance={'helper_sha256': '0' * 64})

    def setUp(self):
        self.modules = patch.dict(sys.modules); self.modules.start()
        for name in base.SOURCES:
            sys.modules.pop(name, None)

    def tearDown(self):
        self.modules.stop()

    def test_real_parsers_binary_shell_and_private_custody(self):
        ctx = self.context(); result = i.inspect(**ctx)
        self.assertEqual(result['status'], 'prestart_inspected')
        self.assertTrue(result['target']['settings_foreground'])
        self.assertTrue(result['target']['unlocked'])
        self.assertTrue(result['camera_preview_progress_verified'])
        self.assertEqual(result['target']['native_mode']['native_actual_hz'], 120)
        self.assertEqual(result['camera_preview_profile']['crop'], [0, 0, 4080, 3072])
        self.assertFalse(result['recording_geometry_qualified'])
        self.assertFalse(result['capture_admitted'])
        self.assertTrue(result['visual_review_required'])
        self.assertEqual(set(ctx['sink'].files), {'target.png', 'camera.png', 'inspection.json'})
        receipt = json.loads(ctx['sink'].files['inspection.json'])
        self.assertEqual(receipt['roles']['target']['boot_id_after'], fixtures.BOOT)
        self.assertEqual(receipt['screenshot_custody']['target']['sha256'], hashlib.sha256(png()).hexdigest())
        for secret in ('target-private', 'camera-private', fixtures.BOOT, 'synthetic-session', 'session_token'):
            self.assertNotIn(secret, json.dumps(result))
        shots = [c for c in ctx['adapter'].extra_calls if c[1] == 'screencap -p']
        self.assertEqual(shots, [('7', 'screencap -p', 15), ('9', 'screencap -p', 15)])

    def test_unknown_lock_never_unlocks_and_nonsettings_not_scene(self):
        self.assertIsNone(i.scene('', '', 'unrecognized')['unlocked'])
        ctx = self.context(); ctx['adapter'].extra['lock'] = 'unknown'
        ctx['adapter'].extra['activity'] = 'mResumedActivity: ActivityRecord{123 u0 private.package/.Secret}'
        result = i.inspect(**ctx)
        self.assertIsNone(result['target']['unlocked'])
        self.assertFalse(result['target']['settings_foreground'])
        self.assertNotIn('private.package', json.dumps(result))

    def test_native_unsupported_fails_no_screenshot(self):
        ctx = self.context(); ctx['adapter'].extra['native'] = 'no anchor'
        with self.assertRaisesRegex(ValueError, '^prestart_inspection_failed$'):
            i.inspect(**ctx)
        self.assertEqual(ctx['sink'].files, {})
        self.assertTrue(ctx['sink'].closed)

    def test_invalid_png_keeps_failure_sanitized(self):
        ctx = self.context(); original = ctx['adapter'].shell
        def shell(tid, command, timeout):
            return (0, b'PRIVATE_INVALID_PNG', b'') if command == 'screencap -p' else original(tid, command, timeout)
        ctx['adapter'].shell = shell
        with self.assertRaisesRegex(ValueError, '^prestart_inspection_failed$'):
            i.inspect(**ctx)
        self.assertNotIn('inspection.json', ctx['sink'].files)

    def test_ast_source_tamper_refused_and_no_trial_import(self):
        name, (path, digest) = next(iter(i.PARSER_SOURCES.items()))
        with self.assertRaises(ValueError):
            i.extracted_parser((ROOT / path).read_bytes() + b'\n', name, digest)
        tree = ast.parse(Path(i.__file__).read_text())
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls.intersection({'setup', 'execute', 'restore', 'reboot', 'sync', 'chmod', 'unlink', 'system'}))
        for command in i.COMMANDS.values():
            self.assertNotIn(' > ', command)
            self.assertNotIn('settings put', command)
            self.assertNotIn('input ', command)

    def test_embedded_pure_api_needs_no_transport(self):
        ctx = self.context(); data = ctx['adapter'].extra
        state = i.validate_native_scene(data['native'], data['software'], data['activity'],
            data['focus'], data['lock'], parsers=ctx['parsers'])
        self.assertTrue(state['settings_foreground'])
        self.assertEqual(i.validate_png(png())['sha256'], hashlib.sha256(png()).hexdigest())
        self.assertFalse(ctx['adapter'].calls)
        self.assertFalse(ctx['adapter'].extra_calls)

    def test_boot_change_after_screenshots_rejects_receipt(self):
        ctx = self.context(); original = ctx['adapter'].shell; count = 0
        def shell(tid, command, timeout):
            nonlocal count
            if command == i.COMMANDS['boot']:
                count += 1
                if count > 6:
                    return 0, b'87654321-1234-1234-1234-123456789abc', b''
            return original(tid, command, timeout)
        ctx['adapter'].shell = shell
        with self.assertRaisesRegex(ValueError, '^prestart_inspection_failed$'):
            i.inspect(**ctx)
        self.assertEqual(set(ctx['sink'].files), {'target.png', 'camera.png'})

    def test_camera_no_progress_rejected_private_images_retained(self):
        ctx = self.context(); original = ctx['adapter'].shell; previous = None
        def shell(tid, command, timeout):
            nonlocal previous
            result = original(tid, command, timeout)
            if command == i.COMMANDS['metadata']:
                if previous is None:
                    previous = result
                return previous
            return result
        ctx['adapter'].shell = shell
        with self.assertRaisesRegex(ValueError, '^prestart_inspection_failed$'):
            i.inspect(**ctx)
        self.assertEqual(set(ctx['sink'].files), {'target.png', 'camera.png'})

    def test_concrete_source_construction_no_socket_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixtures.LauncherTests().fixture(directory)
            config['source_commit'] = i.COMMIT
            path = Path(directory, 'config.json'); path.write_text(json.dumps(config)); path.chmod(0o600)
            def git(args, **kwargs):
                query = args[-1]
                if query == 'HEAD':
                    raw = i.COMMIT.encode()
                else:
                    data = (ROOT / query.split(':', 1)[1]).read_bytes()
                    raw = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest().encode()
                return subprocess.CompletedProcess(args, 0, raw)
            with patch('socket.socket', side_effect=AssertionError('device forbidden')), patch.object(i.subprocess, 'run', side_effect=git):
                result = i.prepare(source_root=str(ROOT), launch_path=str(Path(i.__file__).with_name('launch.py')),
                    probe_path=str(Path(base.__file__)), config_path=str(path),
                    helper_sha=hashlib.sha256(Path(i.__file__).read_bytes()).hexdigest())
            self.assertEqual(type(result['adapter']).__name__, 'OfflineBaselineADB')
            self.assertEqual(set(result['parsers']), {'native_state', 'software_hz'})
            self.assertFalse(Path(directory, i.CHILD).exists())

class PrivateImageTests(unittest.TestCase):
    def config(self, directory):
        meta = os.stat(directory)
        return {'host_uid': os.getuid(), 'evidence': {'directory': directory, 'device': meta.st_dev, 'inode': meta.st_ino}}

    def test_private_modes_custody_and_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = self.config(directory); sink = i.EvidenceChild(cfg); sink.open()
            receipt = sink.write('target.png', png())
            image = Path(directory, i.CHILD, 'target.png')
            self.assertEqual(image.stat().st_ino, receipt['inode'])
            self.assertEqual(stat.S_IMODE(image.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                sink.write('target.png', png())
            sink.close()
            second = i.EvidenceChild(cfg)
            with self.assertRaises(FileExistsError):
                second.open()
            second.close()
            self.assertEqual(image.read_bytes(), png())

    def test_bad_png_crc_bounds_trailing(self):
        self.assertEqual(i.png_info(png())['width'], 1)
        for raw in (png() + b'trailing', png()[:-1] + b'X', b'private', b'x' * (i.MAX_PNG + 1)):
            with self.assertRaises(ValueError):
                i.png_info(raw)

if __name__ == '__main__':
    unittest.main()
