#!/usr/bin/env python3
"""Externally pinned, one-shot READ-ONLY supplemental inspection. No setup.

Uses the real OfflineBaselineADB.shell(tid, fixed_command, timeout) binary API.
Never imports a Trial. Screenshots/evidence stay in a fresh private child.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
import socket
import stat
import struct
import subprocess
import sys
import time
from types import MappingProxyType, ModuleType
import zlib

COMMIT = 'd5a522ce002ca580c231fc87250c38d1665980d3'
LAUNCH_SHA = 'da270f0de24d5fe769b6f876dffd18b7f972c3608ebee3e7f80b60a96164e826'
PROBE_SHA = 'd72d1f8dd25605e3dae9d2b1ad95a753494423d0b150918dcc2495f963b909b1'
PARSER_SOURCES = MappingProxyType({
    'native_state': ('06-tools/dsi_trial_transaction.py', '4407a55b3bc37e197e48c74673cff0626345124ca5163b4177ade9a567339ffa'),
    'software_hz': ('06-tools/stock_c1_sweep.py', '1c105480c1ec7abded156f16cf96a98719f0528620b176698dc4226bf933a0d4'),
})
COMMANDS = MappingProxyType({
    'boot': 'cat /proc/sys/kernel/random/boot_id',
    'native': "su -c dmesg", 'software': 'dumpsys display',
    'lock': 'dumpsys window policy', 'focus': 'dumpsys window windows',
    'activity': 'dumpsys activity activities', 'metadata': 'dumpsys media.camera',
    'screenshot': 'screencap -p',
})
MAX_PNG = 16 * 1024 * 1024
CHILD = 'prestart-inspection'

def require(ok):
    if not ok:
        raise ValueError('prestart_inspection_rejected')

def png_info(raw):
    """Bounded PNG framing/CRC, not visual content or video-resolution approval."""
    require(type(raw) is bytes and 45 <= len(raw) <= MAX_PNG and raw[:8] == b'\x89PNG\r\n\x1a\n')
    pos, ihdr, data_seen, ended = 8, None, False, False
    while pos < len(raw):
        require(pos + 12 <= len(raw))
        size = struct.unpack('>I', raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        require(size <= MAX_PNG and pos + 12 + size <= len(raw))
        content = raw[pos + 8:pos + 8 + size]
        crc = struct.unpack('>I', raw[pos + 8 + size:pos + 12 + size])[0]
        require(zlib.crc32(kind + content) & 0xffffffff == crc)
        if ihdr is None:
            require(kind == b'IHDR' and size == 13)
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', content)
            require(0 < width <= 8192 and 0 < height <= 8192 and width * height <= 32 * 1024 * 1024)
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0)
            ihdr = {'width': width, 'height': height}
        elif kind == b'IHDR':
            require(False)
        if kind == b'IDAT':
            data_seen = True
        if kind == b'IEND':
            require(size == 0 and data_seen and pos + 12 == len(raw))
            ended = True
        pos += size + 12
    require(ended)
    return {**ihdr, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def extracted_parser(raw, name, expected):
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected)
    tree = ast.parse(raw)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(selected) == 1 and not selected[0].decorator_list)
    scope = {'re': re, 'check': lambda ok, message: require(ok)}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<pinned-pure-parser>', 'exec'), scope)
    return scope[name]

def unique(pattern, text):
    found = re.findall(pattern, text, re.M)
    return found[0] if len(found) == 1 else None

def scene(activity, focus, lock):
    resumed = re.findall(r'^.*mResumedActivity:.*\s([A-Za-z0-9_.]+)/[^\s}]+.*$', activity, re.M)
    focused = re.findall(r'^\s*mCurrentFocus=Window\{[^\n]*\s([A-Za-z0-9_.]+)/[^\s}]+[^\n]*\}\s*$', focus, re.M)
    is_settings = (resumed == ['com.android.settings'] and focused == ['com.android.settings'])
    showing = re.findall(r'^\s*(?:mShowingLockscreen|showing)=(true|false)\s*$', lock, re.M)
    restricted = unique(r'^\s*inputRestricted=(true|false)\s*$', lock)
    # Unknown/ambiguous layouts never turn into an unlocked assertion.
    unlocked = (showing[0] == 'false' and restricted == 'false') if len(showing) == 1 and restricted else None
    return {'settings_foreground': is_settings, 'unlocked': unlocked}

def validate_native_scene(native_log, display, activity, focus, lock, *, parsers):
    """Pure embedded coordinator API; supplied parsers must be exact-source-bound.

    Returns observations, not a capture admission or visual scene judgment.
    Caller uses the SAME bound adapter for fixed reads and independently reviews
    the new retained screenshots. No transport, config, lifecycle or mutex call.
    """
    require(set(parsers) == {'native_state', 'software_hz'})
    native = parsers['native_state'](native_log)
    software = parsers['software_hz'](display)
    require(type(software) is float and math.isfinite(software) and 0 < software <= 240)
    return {'native_mode': native, 'software_hz': software, **scene(activity, focus, lock)}

validate_png = png_info

class EvidenceChild:
    """Fresh host-only private child; no overwrite, retry, repair or deletion."""
    def __init__(self, config, api=os):
        self.config, self.api = config, api
        self.parent = self.child = None
        self.child_pin = None
        self.spent = False

    def check(self):
        api, cfg = self.api, self.config
        parent = api.fstat(self.parent)
        require((parent.st_dev, parent.st_ino, parent.st_uid, parent.st_mode) ==
            (cfg['evidence']['device'], cfg['evidence']['inode'], cfg['host_uid'], stat.S_IFDIR | 0o700))
        child = api.fstat(self.child)
        linked = api.stat(CHILD, dir_fd=self.parent, follow_symlinks=False)
        require((child.st_dev, child.st_ino, child.st_uid, child.st_mode) == self.child_pin)
        require((linked.st_dev, linked.st_ino, linked.st_uid, linked.st_mode) == self.child_pin)

    def open(self):
        require(not self.spent)
        self.spent = True
        api, cfg = self.api, self.config
        fd = api.open('/', api.O_RDONLY | api.O_DIRECTORY | api.O_CLOEXEC)
        try:
            for part in cfg['evidence']['directory'].split('/')[1:]:
                require(part and part not in ('.', '..'))
                nxt = api.open(part, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=fd)
                old, fd = fd, nxt; api.close(old)
            self.parent, fd = fd, None
            parent = api.fstat(self.parent)
            require((parent.st_dev, parent.st_ino, parent.st_uid, parent.st_mode) ==
                (cfg['evidence']['device'], cfg['evidence']['inode'], cfg['host_uid'], stat.S_IFDIR | 0o700))
            api.mkdir(CHILD, 0o700, dir_fd=self.parent)
            self.child = api.open(CHILD, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=self.parent)
            child = api.fstat(self.child)
            require(child.st_uid == cfg['host_uid'] and child.st_mode == stat.S_IFDIR | 0o700)
            self.child_pin = (child.st_dev, child.st_ino, child.st_uid, child.st_mode)
            self.check()
        finally:
            if fd is not None:
                api.close(fd)

    def write(self, name, raw):
        require(name in ('target.png', 'camera.png', 'inspection.json'))
        require(type(raw) is bytes and 0 < len(raw) <= (65536 if name.endswith('.json') else MAX_PNG))
        self.check()
        api = self.api
        fd = api.open(name, api.O_WRONLY | api.O_CREAT | api.O_EXCL | api.O_NOFOLLOW | api.O_CLOEXEC, 0o600, dir_fd=self.child)
        try:
            before = api.fstat(fd)
            require(before.st_uid == self.config['host_uid'] and before.st_mode == stat.S_IFREG | 0o600
                    and before.st_size == 0 and before.st_nlink == 1)
            view = memoryview(raw)
            while view:
                count = api.write(fd, view)
                require(type(count) is int and 0 < count <= len(view)); view = view[count:]
            after = api.fstat(fd); linked = api.stat(name, dir_fd=self.child, follow_symlinks=False)
            for observed in (after, linked):
                require((observed.st_dev, observed.st_ino, observed.st_mode, observed.st_uid, observed.st_size, observed.st_nlink) ==
                    (before.st_dev, before.st_ino, before.st_mode, before.st_uid, len(raw), 1))
            self.check()
            return {'device': before.st_dev, 'inode': before.st_ino, 'size': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'mode': before.st_mode, 'uid': before.st_uid}
        finally:
            api.close(fd)

    def close(self):
        failed = False
        for name in ('child', 'parent'):
            fd = getattr(self, name)
            setattr(self, name, None)
            if fd is not None:
                try:
                    self.api.close(fd)
                except BaseException:
                    failed = True
        require(not failed)

class BaselineEvidence:
    def __init__(self, sink):
        self.sink = sink
        self.value = None
    def validate(self):
        self.sink.check()
    def write(self, value):
        require(self.value is None)
        self.value = value

def preview(parser, raw, previous=None):
    scope, _ = parser._selected_scope(raw, '0')
    part = parser._between(scope, '    Latest received frame:\n', '  Device dump:\n', 'result')
    actual = parser._metadata(part, result=True)
    require(actual['frame_duration_ns'] > 0)
    snapshot = parser.validate_capture(raw, previous=previous,
        exposure_ns=actual['exposure_ns'], iso=actual['iso'], focus_diopters=actual['focus_diopters'],
        crop=tuple(actual['crop']), zoom=actual['zoom'], expected_fps=1e9 / actual['frame_duration_ns'])
    require(snapshot['recording_verified'] is False and
            snapshot['request']['capture_intent'] == snapshot['result']['capture_intent'] == 'PREVIEW' and
            not any(s['consumer_kind'] in parser.ENCODER_CONSUMERS for s in snapshot['streams']))
    return snapshot

def inspect(*, base, modules, adapter, serials, config, parsers, sink, provenance,
            clock=time.monotonic, utc=lambda: datetime.now(timezone.utc).isoformat()):
    """One operation attempt. Caller source-binds all inputs before invoking."""
    begin = utc()
    try:
        sink.open()
        memory = BaselineEvidence(sink)
        baseline = base.Observation(adapter, serials, modules['camera_capture_metadata'], memory, clock,
            {'commit': config['source_commit'], 'sha256': config['source_sha256']}).run()
        roles = memory.value['roles']
        def read(role, operation, binary=False):
            require(role in ('target', 'camera') and operation in COMMANDS)
            require(operation in ('boot', 'screenshot') or
                    role == ('camera' if operation == 'metadata' else 'target'))
            rc, out, err = adapter.shell(roles[role]['transport_alias'], COMMANDS[operation], 15)
            require(type(rc) is int and rc == 0 and type(out) is bytes and type(err) is bytes and not err)
            require(len(out) <= MAX_PNG)
            return out if binary else out.decode('utf-8', errors='strict').strip()
        def boots():
            found = {role: read(role, 'boot') for role in roles}
            require(all(found[r] == roles[r]['boot_id_after'] for r in roles))
            return found
        def target():
            return validate_native_scene(read('target', 'native'), read('target', 'software'),
                read('target', 'activity'), read('target', 'focus'), read('target', 'lock'), parsers=parsers)
        before_boots = boots()
        first_target = target()
        parser = modules['camera_capture_metadata']
        first_camera = preview(parser, read('camera', 'metadata'))
        images, custody = {}, {}
        for role in ('target', 'camera'):
            raw = read(role, 'screenshot', True)
            images[role] = {'file': role + '.png', **png_info(raw)}
            custody[role] = sink.write(role + '.png', raw)
        final_camera = preview(parser, read('camera', 'metadata'), first_camera)
        last_target = target()
        after_boots = boots()
        require(first_target == last_target and before_boots == after_boots)
        for role, serial in zip(('target', 'camera'), serials):
            require(adapter.bind(roles[role]['transport_alias']) == serial)
        numeric_profile = {k: final_camera['result'][k] for k in
            ('exposure_ns', 'iso', 'focus_diopters', 'zoom', 'crop', 'frame_duration_ns')}
        streams = [{k: s[k] for k in ('width', 'height', 'pixel_format', 'consumer_kind', 'requested')}
                   for s in final_camera['streams']]
        summary = {'schema': 1, 'status': 'prestart_inspected', 'begin_utc': begin, 'end_utc': utc(),
            'boot_stable': True, 'target': last_target, 'baseline': baseline,
            'camera_preview_progress_verified': final_camera['progress_verified'],
            'camera_preview_profile': numeric_profile, 'camera_preview_streams': streams,
            'screenshots': images, 'visual_review_required': True,
            'recording_geometry_qualified': False, 'capture_admitted': False, 'pwm_hz': None}
        sink.write('inspection.json', json.dumps({'schema': 1, 'source_provenance': provenance,
            'roles': roles, 'inspection_boot_before': before_boots, 'inspection_boot_after': after_boots,
            'screenshot_custody': custody, 'summary': summary,
            'receipt_phase': 'before_descriptor_close'}, allow_nan=False).encode())
        sink.close()
        return {**summary, 'receipt_phase': 'final', 'host_cleanup_verified': True}
    except BaseException:
        try:
            sink.close()
        except BaseException:
            pass
        raise ValueError('prestart_inspection_failed') from None

def prepare(*, source_root, launch_path, probe_path, config_path, helper_sha):
    """Concrete source-bound construction with actual transport API, no I/O to devices."""
    require(re.fullmatch('[0-9a-f]{64}', helper_sha) is not None)
    # Bootstrap file checks before running its code; helper itself needs external authentication.
    def plain(path, expected):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            meta = os.fstat(fd); require(stat.S_ISREG(meta.st_mode) and 0 < meta.st_size <= 256 * 1024)
            raw = os.read(fd, meta.st_size + 1)
            require(len(raw) == meta.st_size and hashlib.sha256(raw).hexdigest() == expected)
            return raw
        finally:
            os.close(fd)
    require(hashlib.sha256(plain(__file__, helper_sha)).hexdigest() == helper_sha)
    launcher = ModuleType('inspection_verified_launcher')
    exec(compile(plain(launch_path, LAUNCH_SHA), launch_path, 'exec', dont_inherit=True), launcher.__dict__)
    config = launcher.parse_config(launcher.read_file(config_path, 16384, private=True))
    require(config['source_commit'] == COMMIT and config['source_sha256']['probe'] == PROBE_SHA)
    base_name = 'inspection_verified_probe'
    require(base_name not in sys.modules)
    base = ModuleType(base_name); base.__file__ = probe_path; sys.modules[base_name] = base
    exec(compile(plain(probe_path, PROBE_SHA), probe_path, 'exec', dont_inherit=True), base.__dict__)
    require(type(source_root) is str and source_root.startswith('/') and not source_root.endswith('/'))
    require(all(part and part not in ('.', '..') for part in source_root.split('/')[1:]))
    def git(*args):
        value = subprocess.run(['/usr/bin/git', '-C', source_root, *args], capture_output=True, timeout=10, check=False)
        require(value.returncode == 0 and len(value.stdout) <= 65536)
        return value.stdout.strip().decode('ascii')
    require(git('rev-parse', '--verify', 'HEAD') == COMMIT)
    def source(relative, expected):
        raw = launcher.read_file(source_root + '/' + relative, 256 * 1024)
        require(hashlib.sha256(raw).hexdigest() == expected)
        require(git('rev-parse', COMMIT + ':' + relative) ==
                hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest())
        return raw
    raw = {name: source(path, config['source_sha256'][name]) for name, path in base.SOURCES.items()}
    modules = base.load_sources(raw, {name: config['source_sha256'][name] for name in base.SOURCES})
    parsers = {name: extracted_parser(source(path, digest), name, digest)
               for name, (path, digest) in PARSER_SOURCES.items()}
    adb, dep = modules['offline_baseline_adb'], modules['linux_adb_probe_dependencies']
    process = dict(config['process']); process['uids'] = tuple(process['uids']); process['version'] = process['version'].encode('ascii')
    pin = dep.VerifiedPin(process=adb.ProcessIdentity(endpoint=adb.ENDPOINT, **process), **config['association'])
    association = dep.LinuxAssociation(pin=pin, limits=dep.ProcLimits(**config['limits']),
        proc=dep.LinuxProcFS(), monotonic=time.monotonic)
    def no_sink(*args, **kwargs):
        raise ValueError('non_read_operation_rejected')
    serials = tuple(s.encode('ascii') for s in config['serials'])
    adapter = adb.OfflineBaselineADB(expected_process=pin.process, expected_serials=serials,
        acquire=association.acquire_process,
        make_socket=dep.make_socket_factory(socket_factory=socket.socket, monotonic=time.monotonic),
        create_sink=no_sink, expected_destination=config['evidence']['directory'] + '/capture.mp4',
        expected_uid=config['host_uid'], sleep=time.sleep, monotonic=time.monotonic)
    provenance = {'helper_sha256': helper_sha, 'launch_sha256': LAUNCH_SHA, 'probe_sha256': PROBE_SHA,
        'dependency_commit': COMMIT, 'dependency_sha256': config['source_sha256'],
        'parser_source_sha256': {path: digest for path, digest in PARSER_SOURCES.values()}}
    return dict(base=base, modules=modules, adapter=adapter, serials=serials, config=config,
                parsers=parsers, sink=EvidenceChild(config), provenance=provenance)

def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only prestart screenshots/mode/scene inspection')
    for key in ('source-root', 'readonly-launch', 'readonly-probe', 'private-config', 'helper-sha256'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--execute-read-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        prepared = prepare(source_root=args.source_root, launch_path=args.readonly_launch,
            probe_path=args.readonly_probe, config_path=args.private_config, helper_sha=args.helper_sha256)
        result = inspect(**prepared) if args.execute_read_only else {
            'status': 'prestart_source_checked', 'device_services_sent': 0, 'capture_admitted': False}
        print(json.dumps(result, allow_nan=False, separators=(',', ':')))
        return 0
    except BaseException:
        print('{"status":"prestart_inspection_failed","capture_admitted":false}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
