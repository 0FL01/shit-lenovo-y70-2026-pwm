#!/usr/bin/env python3
"""Externally authenticate THIS launcher before starting trusted Python -I.

Only explicit --execute-read-only permits device reads. Config is private JSON,
not executable Python; no defaults/discovery, credentials, fallback or retries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from types import ModuleType

def require(ok):
    if not ok:
        raise ValueError('invalid_input')

def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys))

def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 2**63 - 1)
    return value

def string(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value))
    return value

def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result

def read_file(path, cap, private=False):
    require(type(path) is str and path.startswith('/') and path != '/')
    parts = path.split('/')[1:]
    require(all(part and part not in ('.', '..') for part in parts))
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            old, directory = directory, nxt
            os.close(old)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap)
            if private:
                parent = os.fstat(directory)
                require(before.st_uid == os.getuid() and before.st_mode == stat.S_IFREG | 0o600
                        and before.st_nlink == 1 and parent.st_uid == os.getuid()
                        and parent.st_mode == stat.S_IFDIR | 0o700)
            data = bytearray()
            while len(data) <= cap:
                block = os.read(fd, min(65536, cap + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            after = os.fstat(fd)
            attrs = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            require(len(data) == before.st_size and all(getattr(before, a) == getattr(after, a) for a in attrs))
            return bytes(data)
        finally:
            os.close(fd)
    finally:
        os.close(directory)

def parse_config(raw):
    config = json.loads(raw, object_pairs_hook=object_pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    exact(config, ('schema', 'source_commit', 'source_sha256', 'process', 'association',
                   'limits', 'serials', 'host_uid', 'evidence'))
    require(type(config['schema']) is int and config['schema'] == 1)
    string(config['source_commit'], '[0-9a-f]{40}')
    exact(config['source_sha256'], ('probe', 'offline_baseline_adb', 'linux_adb_probe_dependencies', 'camera_capture_metadata'))
    for value in config['source_sha256'].values():
        string(value, '[0-9a-f]{64}')
    process = config['process']
    exact(process, ('pid', 'starttime', 'uids', 'executable', 'executable_device',
                    'executable_inode', 'executable_mode', 'executable_uid', 'version'))
    for key in ('pid', 'starttime', 'executable_inode'):
        integer(process[key], 1)
    for key in ('executable_device', 'executable_mode', 'executable_uid'):
        integer(process[key])
    require(type(process['uids']) is list and len(process['uids']) == 4
            and all(type(x) is int and x == 0 for x in process['uids']))
    string(process['executable'], r'/[A-Za-z0-9_./+-]{1,255}')
    require('..' not in process['executable'].split('/'))
    # Existing server version pin, NOT a credential or command to execute.
    string(process['version'], r'Android Debug Bridge version 1\.0\.41\n[\x20-\x7e\n]{1,2048}')
    association = config['association']
    exact(association, ('listener_inode', 'network_namespace', 'executable_sha256', 'executable_size'))
    integer(association['listener_inode'], 1); integer(association['executable_size'], 1)
    string(association['network_namespace'], r'net:\[[1-9][0-9]*\]')
    string(association['executable_sha256'], '[0-9a-f]{64}')
    exact(config['limits'], ('tcp_bytes', 'stat_bytes', 'status_bytes', 'max_pids',
                              'max_fds_per_pid', 'max_total_fds', 'link_bytes'))
    for value in config['limits'].values():
        integer(value, 1); require(value <= 16 * 1024 * 1024)
    require(type(config['serials']) is list and len(config['serials']) == 2)
    for serial in config['serials']:
        string(serial, '[A-Za-z0-9_.-]{1,256}'); require(serial != 'unknown')
    require(len(set(config['serials'])) == 2)
    integer(config['host_uid']); require(config['host_uid'] == os.getuid())
    exact(config['evidence'], ('directory', 'device', 'inode'))
    string(config['evidence']['directory'], r'/[A-Za-z0-9_./-]{1,512}')
    require(all(x and x not in ('.', '..') for x in config['evidence']['directory'].split('/')[1:]))
    integer(config['evidence']['device']); integer(config['evidence']['inode'], 1)
    return config

def prepare(root, probe_path, config):
    require(type(root) is str and root.startswith('/') and not root.endswith('/'))
    require(all(x and x not in ('.', '..') for x in root.split('/')[1:]))
    # Fixed argv, read-only Git, no shell. No user aliases or network operation.
    def git(*args):
        result = subprocess.run(['/usr/bin/git', '-C', root, *args], capture_output=True,
                                timeout=10, check=False)
        require(result.returncode == 0 and len(result.stdout) <= 65536)
        return result.stdout.strip().decode('ascii')
    require(git('rev-parse', '--verify', 'HEAD') == config['source_commit'])
    path = probe_path
    probe_raw = read_file(path, 256 * 1024)
    require(hashlib.sha256(probe_raw).hexdigest() == config['source_sha256']['probe'])
    require('stock_readonly_probe' not in sys.modules)
    module = ModuleType('stock_readonly_probe')
    module.__file__ = path
    sys.modules[module.__name__] = module
    exec(compile(probe_raw, path, 'exec', dont_inherit=True), module.__dict__)
    raw = {}
    for name, relative in module.SOURCES.items():
        raw[name] = read_file(root + '/' + relative, 256 * 1024)
        blob = git('rev-parse', config['source_commit'] + ':' + relative)
        observed = hashlib.sha1(b'blob ' + str(len(raw[name])).encode() + b'\0' + raw[name]).hexdigest()
        require(blob == observed)
    modules = module.load_sources(raw, {k: config['source_sha256'][k] for k in module.SOURCES})
    adb, dep = modules['offline_baseline_adb'], modules['linux_adb_probe_dependencies']
    process = dict(config['process'])
    process['uids'] = tuple(process['uids']); process['version'] = process['version'].encode('ascii')
    pin = dep.VerifiedPin(process=adb.ProcessIdentity(endpoint=adb.ENDPOINT, **process), **config['association'])
    evidence = config['evidence']
    inputs = module.PrivateInputs(pin, dep.ProcLimits(**config['limits']),
        tuple(x.encode('ascii') for x in config['serials']), config['host_uid'],
        evidence['directory'], evidence['device'], evidence['inode'])
    observation = module.construct(modules=modules, inputs=inputs, proc=dep.LinuxProcFS(),
        source_provenance={'commit': config['source_commit'], 'sha256': config['source_sha256']},
        socket_factory=socket.socket, monotonic=time.monotonic, sleep=time.sleep)
    return observation

def main(argv=None):
    parser = argparse.ArgumentParser(description='Pinned read-only readiness observer; no setup/capture.')
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--private-config', required=True)
    parser.add_argument('--probe-source', required=True)
    parser.add_argument('--execute-read-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = parse_config(read_file(args.private_config, 16384, private=True))
        observation = prepare(args.source_root, args.probe_source, config)
        if args.execute_read_only:
            result = observation.run()
        else:
            result = {'status': 'source_and_config_checked', 'device_services_sent': 0,
                      'setup_admitted': False, 'acquisition_qualified': False}
        print(json.dumps(result, allow_nan=False, separators=(',', ':')))
        return 0
    except BaseException:
        print('{"status":"read_only_probe_failed","setup_admitted":false,"acquisition_qualified":false}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
