"""Inactive read-only observation API. No CLI, device I/O at import, or trial.

Externally authenticate this file BEFORE import. All dependencies below must be
externally pinned bytes. Private inputs are never learned from observations.
This is not a security sandbox against malicious trusted Python/host/root.
"""
import builtins
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
import shlex
import stat
import sys
from types import MappingProxyType, ModuleType

SOURCES = MappingProxyType({
    'offline_baseline_adb': '06-tools/host_adb_full_api_spike/offline_baseline_adb.py',
    'linux_adb_probe_dependencies': '06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py',
    'camera_capture_metadata': '06-tools/camera_capture_metadata.py',
})
TARGET = ('XT2611-1', 'W3WWS36.65-64-4-1', '_b',
          '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k', 'Enforcing', 'avr')
CAMERA = ('Galaga', 'ROW', 'A001')
PANEL = 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
MODULE = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
KEYS = ('screen_brightness', 'screen_brightness_mode', 'min_refresh_rate',
        'peak_refresh_rate', 'screen_off_timeout')
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
LOCK = '/data/local/tmp/legion-pwm-research.lock'

def root(command):
    return 'su -c ' + shlex.quote(command)

# No caller-provided command, path, property name, or operation is interpolated.
COMMANDS = MappingProxyType({
    'boot': 'cat /proc/sys/kernel/random/boot_id',
    'target_identity': 'getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce; getprop ro.product.device',
    'camera_identity': 'getprop ro.product.device; getprop ro.boot.hardware.sku; getprop ro.product.model',
    'root': root('id -u'),
    'panel': root('cat ' + CON + 'panelName'),
    'module': root('sha256sum /vendor/lib/modules/msm_drm.ko'),
    'native': root('cat ' + BL + 'brightness; cat ' + BL + 'bl_power; cat ' + CON + 'panelDC; cat ' + CON + 'mipi_cmd_log_en'),
    'settings': '; '.join('settings get system ' + key for key in KEYS),
    'mutex': root('if test -e ' + LOCK + ' || test -L ' + LOCK + '; then echo present; else echo absent; fi'),
    'power': 'dumpsys power',
    'window': 'dumpsys window policy',
    'foreground': 'dumpsys activity activities',
    'package': 'dumpsys package net.sourceforge.opencamera',
    'metadata': 'dumpsys media.camera',
})
ROLES = MappingProxyType({key: ('target', 'camera') if key == 'boot' else
    ('camera',) if key in ('camera_identity', 'package', 'metadata') else ('target',)
    for key in COMMANDS})

class Rejected(RuntimeError):
    """Only static sanitized errors may leave this module."""

def need(value):
    if not value:
        raise Rejected('read_only_probe_rejected')

def load_sources(raw, expected_sha256):
    """Fixed three-module byte DAG, independently pinned by the operator.

    Caller verifies clean tracked commit/provenance separately before supplying
    bytes. A self-generated digest map is not approval. No filesystem discovery.
    """
    need(type(raw) is dict and type(expected_sha256) is dict)
    need(set(raw) == set(SOURCES) == set(expected_sha256))
    need(not set(SOURCES).intersection(sys.modules))
    for name in SOURCES:
        need(type(raw[name]) is bytes and len(raw[name]) <= 256 * 1024)
        digest = expected_sha256[name]
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest))
        need(hashlib.sha256(raw[name]).hexdigest() == digest)
    loaded = {}
    original_import = builtins.__import__
    def fixed_import(name, globals=None, locals=None, fromlist=(), level=0):
        need(level == 0)
        if name in SOURCES:
            need(name in loaded)
            return loaded[name]
        need(name.split('.')[0] in sys.stdlib_module_names)
        return original_import(name, globals, locals, fromlist, level)
    try:
        for name, path in SOURCES.items():
            module = ModuleType(name)
            module.__file__ = path
            module.__builtins__ = {**vars(builtins), '__import__': fixed_import}
            sys.modules[name] = module
            loaded[name] = module
            exec(compile(raw[name], path, 'exec', dont_inherit=True), module.__dict__)
        return MappingProxyType(loaded)
    except BaseException:
        for name, module in loaded.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]
        raise Rejected('source_load_rejected') from None

@dataclass(frozen=True, repr=False)
class PrivateInputs:
    pin: object
    limits: object
    serials: tuple
    host_uid: int
    evidence_directory: str
    evidence_device: int
    evidence_inode: int

class PrivateEvidence:
    """Fresh exclusive file under an independently pinned existing 0700 dir.

    Trusted same UID/root and no concurrent namespace mutation are assumptions.
    No mkdir/chmod/delete/overwrite. Partial evidence is retained after failure.
    """
    def __init__(self, inputs, os_api=os):
        self.os = os_api
        self.inputs = inputs
        self.spent = False

    def validate(self):
        """Reject inaccessible/wrong/private-existing sink before device I/O."""
        api, cfg = self.os, self.inputs
        fd = api.open('/', api.O_RDONLY | api.O_DIRECTORY | api.O_CLOEXEC)
        try:
            for part in cfg.evidence_directory.split('/')[1:]:
                nxt = api.open(part, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=fd)
                old, fd = fd, nxt
                api.close(old)
            meta = api.fstat(fd)
            need((meta.st_dev, meta.st_ino, meta.st_uid, meta.st_mode) ==
                 (cfg.evidence_device, cfg.evidence_inode, cfg.host_uid, stat.S_IFDIR | 0o700))
            try:
                api.stat('readiness.json', dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                need(False)
        finally:
            api.close(fd)

    def write(self, evidence):
        need(not self.spent)
        self.spent = True
        api, cfg = self.os, self.inputs
        data = json.dumps(evidence, allow_nan=False, separators=(',', ':')).encode()
        need(len(data) <= 65536)
        # Walk every component without following symlinks; keep final dirfd.
        fd = api.open('/', api.O_RDONLY | api.O_DIRECTORY | api.O_CLOEXEC)
        try:
            for part in cfg.evidence_directory.split('/')[1:]:
                nxt = api.open(part, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=fd)
                old, fd = fd, nxt
                api.close(old)
            before = api.fstat(fd)
            need((before.st_dev, before.st_ino, before.st_uid, before.st_mode) ==
                 (cfg.evidence_device, cfg.evidence_inode, cfg.host_uid, stat.S_IFDIR | 0o700))
            file_fd = api.open('readiness.json', api.O_WRONLY | api.O_CREAT | api.O_EXCL |
                               api.O_NOFOLLOW | api.O_CLOEXEC, 0o600, dir_fd=fd)
            try:
                meta = api.fstat(file_fd)
                need(meta.st_uid == cfg.host_uid and meta.st_mode == stat.S_IFREG | 0o600
                     and meta.st_nlink == 1 and meta.st_size == 0)
                view = memoryview(data)
                while view:
                    count = api.write(file_fd, view)
                    need(type(count) is int and 0 < count <= len(view))
                    view = view[count:]
                after = api.fstat(file_fd)
                linked = api.stat('readiness.json', dir_fd=fd, follow_symlinks=False)
                need((after.st_dev, after.st_ino, after.st_uid, after.st_mode, after.st_nlink, after.st_size) ==
                     (meta.st_dev, meta.st_ino, cfg.host_uid, stat.S_IFREG | 0o600, 1, len(data)))
                need((linked.st_dev, linked.st_ino) == (meta.st_dev, meta.st_ino))
                final = api.fstat(fd)
                need((final.st_dev, final.st_ino, final.st_uid, final.st_mode) ==
                     (before.st_dev, before.st_ino, before.st_uid, before.st_mode))
            finally:
                api.close(file_fd)
        finally:
            api.close(fd)

def construct(*, modules, inputs, source_provenance, proc, socket_factory, monotonic, sleep, os_api=os):
    """Inert construction. Never run this on a device host without admission."""
    need(type(inputs) is PrivateInputs and set(modules) == set(SOURCES))
    need(type(source_provenance) is dict and set(source_provenance) == {'commit', 'sha256'})
    need(type(source_provenance['commit']) is str and re.fullmatch('[0-9a-f]{40}', source_provenance['commit']))
    need(type(source_provenance['sha256']) is dict and set(source_provenance['sha256']) == set(SOURCES) | {'probe'})
    need(all(type(x) is str and re.fullmatch('[0-9a-f]{64}', x) for x in source_provenance['sha256'].values()))
    need(type(inputs.host_uid) is int and inputs.host_uid >= 0)
    need(type(inputs.serials) is tuple and len(inputs.serials) == 2)
    need(all(type(s) is bytes and re.fullmatch(rb'[A-Za-z0-9_.-]{1,256}', s)
             and s != b'unknown' for s in inputs.serials))
    need(len(set(inputs.serials)) == 2)
    path = inputs.evidence_directory
    need(type(path) is str and path.startswith('/') and path != '/' and
         all(p and p not in ('.', '..') for p in path.split('/')[1:]))
    need(type(inputs.evidence_device) is int and inputs.evidence_device >= 0 and
         type(inputs.evidence_inode) is int and inputs.evidence_inode > 0)
    dep, adb = modules['linux_adb_probe_dependencies'], modules['offline_baseline_adb']
    need(type(inputs.pin) is dep.VerifiedPin and type(inputs.limits) is dep.ProcLimits)
    # Validate before any syscall or device operation.
    association = dep.LinuxAssociation(pin=inputs.pin, limits=inputs.limits,
                                      proc=proc, monotonic=monotonic)
    def no_sink(*args, **kwargs):
        raise Rejected('non_read_operation_rejected')
    transport = adb.OfflineBaselineADB(expected_process=inputs.pin.process,
        expected_serials=inputs.serials, acquire=association.acquire_process,
        make_socket=dep.make_socket_factory(socket_factory=socket_factory, monotonic=monotonic),
        create_sink=no_sink, expected_destination=path + '/capture.mp4',
        expected_uid=inputs.host_uid, sleep=sleep, monotonic=monotonic)
    return Observation(transport, inputs.serials, modules['camera_capture_metadata'],
                       PrivateEvidence(inputs, os_api), monotonic, source_provenance)

def unique(pattern, value):
    matches = re.findall(pattern, value, re.M)
    return matches[0] if len(matches) == 1 else None

class Observation:
    def __init__(self, transport, serials, parser, sink, clock, source_provenance=None):
        self.__transport = transport
        self.__serials = tuple(serials)
        self.__parser, self.__sink, self.__clock = parser, sink, clock
        self.__spent = False
        self.__provenance = source_provenance

    def run(self):
        """One attempt, static sanitized failure; never retries/rebinds on failure."""
        need(not self.__spent)
        self.__spent = True
        try:
            return self.__run()
        except BaseException:
            # Do not propagate callback errors, serials, raw dumps or tracebacks.
            raise Rejected('read_only_probe_failed') from None

    def __run(self):
        transport = self.__transport
        self.__sink.validate()
        transport.preflight()
        rows = {}
        for line in transport.host('host:devices-l').splitlines():
            fields = line.split()
            need(len(fields) >= 3)
            tids = [f[13:] for f in fields[2:] if f.startswith(b'transport_id:')]
            need(len(tids) == 1 and re.fullmatch(rb'[1-9][0-9]{0,19}', tids[0]))
            need(fields[0] not in rows)
            rows[fields[0]] = (tids[0].decode('ascii'), fields[1])
        need(all(s in rows and rows[s][1] == b'device' for s in self.__serials))
        tids = {role: rows[serial][0] for role, serial in zip(('target', 'camera'), self.__serials)}
        need(len(set(tids.values())) == 2)
        for role, serial in zip(('target', 'camera'), self.__serials):
            need(transport.bind(tids[role]) == serial)
        def query(role, operation):
            need(operation in COMMANDS and role in ROLES[operation])
            rc, out, err = transport.shell(tids[role], COMMANDS[operation], 12)
            need(type(rc) is int and rc == 0 and type(out) is bytes and type(err) is bytes)
            need(not err and len(out) <= 8 * 1024 * 1024)
            return out.decode('utf-8', errors='strict').strip()
        def boots():
            values = {role: query(role, 'boot') for role in tids}
            need(all(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', v) for v in values.values()))
            return values
        before = boots()
        need(tuple(query('target', 'target_identity').splitlines()) == TARGET)
        need(tuple(query('camera', 'camera_identity').splitlines()) == CAMERA)
        need(query('target', 'root') == '0')
        need(query('target', 'panel') == PANEL)
        need(query('target', 'module') == MODULE + '  /vendor/lib/modules/msm_drm.ko')
        settings = query('target', 'settings').splitlines()
        need(len(settings) == 5)
        parsed = {}
        for key, value in zip(KEYS, settings):
            need(re.fullmatch(r'[0-9]{1,8}(?:\.[0-9]{1,6})?', value))
            parsed[key] = float(value) if '.' in value else int(value)
        native = query('target', 'native').splitlines()
        need(len(native) == 4 and all(re.fullmatch('[0-9]{1,8}', x) for x in native[:3]))
        logger = unique(r'^[^\n]*:\s*([01])$', native[3])
        need(logger is not None)
        mutex = query('target', 'mutex')
        need(mutex in ('present', 'absent'))
        power = unique(r'^\s*mWakefulness=(Awake|Asleep|Dozing|Dreaming)\s*$', query('target', 'power'))
        locked = unique(r'^\s*mShowingLockscreen=(true|false)\s*$', query('target', 'window'))
        # Only classify allowlisted component; never publish arbitrary foreground names.
        activity = query('target', 'foreground')
        foreground = unique(r'^.*mResumedActivity:.* (net\.sourceforge\.opencamera|com\.android\.launcher3)/[^\s}]+.*$', activity)
        package = query('camera', 'package')
        version_code = unique(r'^\s*versionCode=([0-9]{1,12})(?:\s.*)?$', package)
        version_name = unique(r'^\s*versionName=([0-9]{1,4}(?:\.[0-9]{1,4}){1,3})\s*$', package)
        # Observe the actual manual profile, then validate request/result agreement
        # with the pinned pure parser. This does NOT approve a capture profile.
        camera_ready, profile = False, None
        metadata = query('camera', 'metadata')
        try:
            scope, _ = self.__parser._selected_scope(metadata, '0')
            result_part = self.__parser._between(scope, '    Latest received frame:\n',
                '  Device dump:\n', 'result')
            actual = self.__parser._metadata(result_part, result=True)
            need(actual['frame_duration_ns'] > 0)
            snapshot = self.__parser.validate_capture(metadata,
                exposure_ns=actual['exposure_ns'], iso=actual['iso'],
                focus_diopters=actual['focus_diopters'], crop=tuple(actual['crop']),
                zoom=actual['zoom'], expected_fps=1e9 / actual['frame_duration_ns'])
            camera_ready = (snapshot['recording_verified'] is False and
                            snapshot['request']['capture_intent'] == 'PREVIEW' and
                            snapshot['result']['capture_intent'] == 'PREVIEW' and
                            not any(s['consumer_kind'] in self.__parser.ENCODER_CONSUMERS
                                    for s in snapshot['streams']))
            if camera_ready:
                profile = {key: snapshot['result'][key] for key in (
                    'exposure_ns', 'iso', 'focus_diopters', 'zoom', 'frame_duration_ns')}
        except self.__parser.CaptureMetadataError:
            pass
        after = boots()
        need(before == after)
        # Revalidate serial selection and pinned process after all reads.
        for role, serial in zip(('target', 'camera'), self.__serials):
            need(transport.bind(tids[role]) == serial)
        summary = {'schema': 1, 'status': 'observed_read_only', 'identity_verified': True,
            'boot_stable_during_probe': True, 'settings': parsed,
            'native_dbv': int(native[0]), 'bl_power': int(native[1]), 'panel_dc': int(native[2]),
            'logger': int(logger), 'mutex': mutex, 'power': power, 'locked': locked,
            'foreground': foreground, 'camera_stopped_preview_verified': camera_ready,
            'camera_profile': profile, 'camera_version_code': int(version_code) if version_code else None,
            'camera_version_name': version_name, 'camera_duration_seconds': None,
            'camera_restart_count': None, 'setup_admitted': False, 'acquisition_qualified': False,
            'pwm_hz': None}
        # Raw metadata/package/window output and camera session tokens are discarded.
        self.__sink.write({'schema': 1, 'roles': {role: {'serial': serial.decode('ascii'),
            'transport_alias': tids[role], 'boot_id_before': before[role], 'boot_id_after': after[role]}
            for role, serial in zip(('target', 'camera'), self.__serials)}, 'summary': summary,
            'source_provenance': self.__provenance})
        return summary
