#!/usr/bin/env python3
"""One-shot HOST deployment wrapper, to be externally authenticated before use.

No SSH, ADB CLI, device mutation, secret discovery, retry or cleanup. Stdin is
strict private JSON. Default creates fresh host files and source-validates only.
--execute-read-only also runs the pinned observer in the SAME one-shot invocation.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
import subprocess
import sys
from types import ModuleType

BASE = '/root'
BASE_PIN = {'device': 64513, 'inode': 1966081, 'mode': 16832, 'uid': 0}
CODE = 'legion-y70-aa-runtime-d5a522c-20261110-01'
CODE_PIN = {'device': 64513, 'inode': 1979034, 'mode': 16832, 'uid': 0}
DEST = 'legion-y70-stock-readonly-2a53eb4-20261110-01'
COMMIT = 'd5a522ce002ca580c231fc87250c38d1665980d3'
HOST_UID = 0
SOURCE_HASHES = {
    'probe': 'd72d1f8dd25605e3dae9d2b1ad95a753494423d0b150918dcc2495f963b909b1',
    'offline_baseline_adb': '17b2cc726497e95e16414192c808fb3eed64cbe64ed87fba39710685a818cf51',
    'linux_adb_probe_dependencies': '9ff5e7ea212d46961c4a74757acc5d50b9d666aa47f9f4e1c58722845bfd53d9',
    'camera_capture_metadata': '8787b7c3f3b4019014204c095529e284a5a06d44ecfce48cda9afbd6bd0ec665',
}
FILE_HASHES = {
    'launch.py': 'da270f0de24d5fe769b6f876dffd18b7f972c3608ebee3e7f80b60a96164e826',
    'probe.py': SOURCE_HASHES['probe'],
}
TOP = {'base_path', 'base_pin', 'code_name', 'code_pin', 'config_without_evidence',
       'files', 'probe_directory_name'}
CONFIG = {'association', 'host_uid', 'limits', 'process', 'schema', 'serials',
          'source_commit', 'source_sha256'}

def require(ok):
    if not ok:
        raise ValueError('deployment_rejected')

def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys))

def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value)
        value[key] = item
    return value

def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 65536)
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))

def pin(value, expected):
    exact(value, expected)
    require(all(type(v) is int for v in value.values()) and value == expected)

def parse_payload(raw):
    payload = decode(raw)
    exact(payload, TOP)
    require(payload['base_path'] == BASE and payload['code_name'] == CODE
            and payload['probe_directory_name'] == DEST)
    pin(payload['base_pin'], BASE_PIN); pin(payload['code_pin'], CODE_PIN)
    exact(payload['files'], FILE_HASHES)
    sources = {}
    for name, approved in FILE_HASHES.items():
        row = payload['files'][name]
        exact(row, ('sha256', 'utf8'))
        require(type(row['sha256']) is str and row['sha256'] == approved)
        require(type(row['utf8']) is str)
        sources[name] = row['utf8'].encode('utf-8')
        require(hashlib.sha256(sources[name]).hexdigest() == approved)
    config = payload['config_without_evidence']
    exact(config, CONFIG)
    require(config['source_commit'] == COMMIT and config['source_sha256'] == SOURCE_HASHES)
    require(type(config['host_uid']) is int and config['host_uid'] == HOST_UID)
    # Execute ONLY the independently pinned inert launch parser, not private code.
    parser = ModuleType('verified_readonly_config_parser')
    exec(compile(sources['launch.py'], '<verified-launch-parser>', 'exec', dont_inherit=True), parser.__dict__)
    provisional = {**config, 'evidence': {'directory': BASE + '/' + DEST + '/evidence',
                                       'device': 0, 'inode': 1}}
    parser.parse_config(json.dumps(provisional))
    return config, sources

def metadata(value):
    return {'device': value.st_dev, 'inode': value.st_ino,
            'mode': value.st_mode, 'uid': value.st_uid}

def check_dir(api, fd, expected):
    pin(metadata(api.fstat(fd)), expected)

def check_edge(api, parent, name, expected):
    pin(metadata(api.stat(name, dir_fd=parent, follow_symlinks=False)), expected)

def write_exclusive(api, parent, name, content):
    require(type(content) is bytes and 0 < len(content) <= 65536)
    fd = api.open(name, api.O_WRONLY | api.O_CREAT | api.O_EXCL | api.O_NOFOLLOW | api.O_CLOEXEC,
                  0o600, dir_fd=parent)
    try:
        before = api.fstat(fd)
        require(before.st_mode == stat.S_IFREG | 0o600 and before.st_uid == HOST_UID
                and before.st_nlink == 1 and before.st_size == 0)
        view = memoryview(content)
        while view:
            count = api.write(fd, view)
            require(type(count) is int and 0 < count <= len(view))
            view = view[count:]
        after = api.fstat(fd)
        linked = api.stat(name, dir_fd=parent, follow_symlinks=False)
        require(metadata(before) == metadata(after) == metadata(linked)
                and after.st_size == linked.st_size == len(content)
                and after.st_nlink == linked.st_nlink == 1)
    finally:
        api.close(fd)

def sanitize_observation(value):
    """Independent output allowlist; never forward arbitrary child dictionaries."""
    keys = {'schema', 'status', 'identity_verified', 'boot_stable_during_probe', 'settings',
        'native_dbv', 'bl_power', 'panel_dc', 'logger', 'mutex', 'power', 'locked', 'foreground',
        'camera_stopped_preview_verified', 'camera_profile', 'camera_version_code',
        'camera_version_name', 'camera_duration_seconds', 'camera_restart_count',
        'setup_admitted', 'acquisition_qualified', 'pwm_hz'}
    exact(value, keys)
    require(type(value['schema']) is int and value['schema'] == 1 and value['status'] == 'observed_read_only')
    for key in ('identity_verified', 'boot_stable_during_probe'):
        require(value[key] is True)
    require(type(value['camera_stopped_preview_verified']) is bool)
    require(value['setup_admitted'] is False and value['acquisition_qualified'] is False)
    for key in ('camera_duration_seconds', 'camera_restart_count', 'pwm_hz'):
        require(value[key] is None)
    for key in ('native_dbv', 'bl_power', 'panel_dc', 'logger'):
        require(type(value[key]) is int and 0 <= value[key] <= 99999999)
    require(value['logger'] in (0, 1))
    require(value['mutex'] in ('present', 'absent'))
    require(value['power'] in (None, 'Awake', 'Asleep', 'Dozing', 'Dreaming'))
    require(value['locked'] in (None, 'true', 'false'))
    require(value['foreground'] in (None, 'net.sourceforge.opencamera', 'com.android.launcher3'))
    import math
    import re
    def number(n):
        require(type(n) in (int, float) and math.isfinite(n) and n >= 0)
    exact(value['settings'], ('screen_brightness', 'screen_brightness_mode',
        'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout'))
    for n in value['settings'].values():
        number(n)
    if value['camera_profile'] is not None:
        exact(value['camera_profile'], ('exposure_ns', 'iso', 'focus_diopters', 'zoom', 'frame_duration_ns'))
        for n in value['camera_profile'].values():
            number(n)
    require(value['camera_version_code'] is None or
            type(value['camera_version_code']) is int and 0 <= value['camera_version_code'] < 10**12)
    name = value['camera_version_name']
    require(name is None or type(name) is str and re.fullmatch(r'[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}', name))
    return value

class Deployment:
    def __init__(self, *, api=os, runner=subprocess.run,
                 utc=lambda: datetime.now(timezone.utc).isoformat()):
        self.api, self.runner, self.utc = api, runner, utc
        self.spent = False

    def run(self, raw, *, execute_read_only=False):
        require(not self.spent and type(execute_read_only) is bool)
        self.spent = True
        result = {'schema': 1, 'outcome': 'failed', 'begin_utc': self.utc(), 'end_utc': None,
            'stage': 'validate_payload', 'source_only_validated': False,
            'read_only_requested': execute_read_only, 'read_only_started': False,
            'setup_admitted': False, 'acquisition_qualified': False, 'observation': None,
            'source_only_begin_utc': None, 'source_only_end_utc': None,
            'read_only_begin_utc': None, 'read_only_end_utc': None,
            'host_cleanup_verified': False, 'receipt_phase': 'pending'}
        owned = []
        dest_fd = None
        api = self.api
        try:
            config, sources = parse_payload(raw)
            require(api.getuid() == HOST_UID and api.geteuid() == HOST_UID)
            root = api.open(BASE, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC)
            owned.append(root); check_dir(api, root, BASE_PIN)
            code = api.open(CODE, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=root)
            owned.append(code); check_dir(api, code, CODE_PIN); check_edge(api, root, CODE, CODE_PIN)
            result['stage'] = 'create_host_files'
            # Exclusive mkdir: EEXIST terminal, including earlier source-only runs.
            api.mkdir(DEST, 0o700, dir_fd=root)
            dest_fd = api.open(DEST, api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=root)
            owned.append(dest_fd)
            dest_pin = metadata(api.fstat(dest_fd))
            require(dest_pin['mode'] == stat.S_IFDIR | 0o700 and dest_pin['uid'] == HOST_UID)
            check_edge(api, root, DEST, dest_pin)
            api.mkdir('evidence', 0o700, dir_fd=dest_fd)
            evidence = api.open('evidence', api.O_RDONLY | api.O_DIRECTORY | api.O_NOFOLLOW | api.O_CLOEXEC, dir_fd=dest_fd)
            owned.append(evidence)
            evidence_pin = metadata(api.fstat(evidence))
            require(evidence_pin['mode'] == stat.S_IFDIR | 0o700 and evidence_pin['uid'] == HOST_UID)
            check_edge(api, dest_fd, 'evidence', evidence_pin)
            config = {**config, 'evidence': {'directory': BASE + '/' + DEST + '/evidence',
                       'device': evidence_pin['device'], 'inode': evidence_pin['inode']}}
            for name, content in sources.items():
                write_exclusive(api, dest_fd, name, content)
            write_exclusive(api, dest_fd, 'config.json', json.dumps(config, allow_nan=False).encode())
            write_exclusive(api, dest_fd, 'begin.json', json.dumps(result, allow_nan=False).encode())
            args = ['/usr/bin/python3', '-I', '-B', BASE + '/' + DEST + '/launch.py',
                    '--source-root', BASE + '/' + CODE, '--probe-source', BASE + '/' + DEST + '/probe.py',
                    '--private-config', BASE + '/' + DEST + '/config.json']
            def child(readonly):
                check_dir(api, root, BASE_PIN); check_dir(api, code, CODE_PIN)
                check_dir(api, dest_fd, dest_pin); check_dir(api, evidence, evidence_pin)
                check_edge(api, root, CODE, CODE_PIN); check_edge(api, root, DEST, dest_pin)
                check_edge(api, dest_fd, 'evidence', evidence_pin)
                completed = self.runner(args + (['--execute-read-only'] if readonly else []),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                    timeout=600 if readonly else 90, check=False)
                require(completed.returncode == 0)
                parsed = decode(completed.stdout)
                check_dir(api, root, BASE_PIN); check_dir(api, code, CODE_PIN)
                check_dir(api, dest_fd, dest_pin); check_dir(api, evidence, evidence_pin)
                check_edge(api, root, CODE, CODE_PIN); check_edge(api, root, DEST, dest_pin)
                check_edge(api, dest_fd, 'evidence', evidence_pin)
                return parsed
            result['stage'] = 'source_only'
            result['source_only_begin_utc'] = self.utc()
            checked = child(False)
            require(checked == {'status': 'source_and_config_checked', 'device_services_sent': 0,
                'setup_admitted': False, 'acquisition_qualified': False})
            require(type(checked['device_services_sent']) is int)
            result['source_only_validated'] = True
            result['source_only_end_utc'] = self.utc()
            if execute_read_only:
                result['stage'] = 'read_only'; result['read_only_started'] = True
                result['read_only_begin_utc'] = self.utc()
                result['observation'] = sanitize_observation(child(True))
                result['read_only_end_utc'] = self.utc()
                result['outcome'] = 'read_only_observed'
            else:
                result['outcome'] = 'source_only_validated'
            result['stage'] = 'complete'
        except subprocess.TimeoutExpired:
            result['outcome'] = 'uncertain'
        except BaseException:
            # Never publish exception text, raw stdout, config or pins.
            result['outcome'] = 'uncertain' if result['read_only_started'] else 'failed'
        finally:
            result['end_utc'] = self.utc()
            if result['source_only_begin_utc'] and not result['source_only_end_utc']:
                result['source_only_end_utc'] = result['end_utc']
            if result['read_only_begin_utc'] and not result['read_only_end_utc']:
                result['read_only_end_utc'] = result['end_utc']
            if dest_fd is not None:
                try:
                    provisional = {**result, 'receipt_phase': 'before_descriptor_close'}
                    write_exclusive(api, dest_fd, 'outcome.json', json.dumps(provisional, allow_nan=False).encode())
                except BaseException:
                    result['outcome'] = 'uncertain' if result['read_only_started'] else 'failed'
                    result['stage'] = 'outcome_write_failed'
            close_ok = True
            for fd in reversed(owned):
                try:
                    api.close(fd)
                except BaseException:
                    close_ok = False
                    result['outcome'] = 'uncertain' if result['read_only_started'] else 'failed'
                    result['stage'] = 'close_failed'
            result['host_cleanup_verified'] = close_ok
            result['receipt_phase'] = 'final'
        return result

def main(argv=None, stdin=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in ([], ['--execute-read-only']):
        print('{"outcome":"failed","stage":"arguments"}')
        return 1
    try:
        raw = (sys.stdin.buffer if stdin is None else stdin).read(65537)
        result = Deployment().run(raw, execute_read_only=bool(argv))
    except BaseException:
        result = {'outcome': 'failed', 'stage': 'stdin'}
    print(json.dumps(result, allow_nan=False, separators=(',', ':')))
    return 0 if result['outcome'] in ('read_only_observed', 'source_only_validated') else 1

if __name__ == '__main__':
    sys.exit(main())
