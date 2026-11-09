#!/usr/bin/env python3
"""Query only an explicitly supplied saved SELinux binary, never live policy.
ABI: SELinuxProject/selinux tag 3.8.1 libsepol public headers.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import re
import resource
import stat
import subprocess
import sys

LIB = '/lib/x86_64-linux-gnu/libsepol.so.2'
MAX_BYTES = 16 * 1024 * 1024
SOURCE = 'https://github.com/SELinuxProject/selinux/tree/3.8.1/libsepol/include/sepol'

class Decision(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ('allowed', 'decided', 'auditallow', 'auditdeny', 'seqno')]

def checked(rc, operation):
    if rc != 0:
        raise ValueError(f'{operation} returned {rc}')

def ascii_arg(value, name, context=False):
    pattern = r'[A-Za-z0-9_:,.-]{1,512}' if context else r'[A-Za-z0-9_]{1,64}'
    if not re.fullmatch(pattern, value, flags=re.ASCII):
        raise ValueError(f'invalid bounded ASCII {name}')
    return value.encode('ascii')

def bind(lib, name, args, result=C.c_int):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result
    return fn

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('policy')
    ap.add_argument('--source-context', required=True)
    ap.add_argument('--target-context', required=True)
    ap.add_argument('--class-name', default='dir')
    ap.add_argument('--permissions', nargs='+', default=['write', 'search'])
    a = ap.parse_args()
    if os.getuid() == 0 or os.geteuid() == 0:
        raise ValueError('run unprivileged')
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if len(a.permissions) > 8:
        raise ValueError('at most 8 permissions')
    sc = ascii_arg(a.source_context, 'source context', True)
    tc = ascii_arg(a.target_context, 'target context', True)
    cl = ascii_arg(a.class_name, 'class')
    perms = [ascii_arg(p, 'permission') for p in a.permissions]
    if (C.sizeof(C.c_uint16), C.sizeof(C.c_uint32), C.sizeof(C.c_uint), C.sizeof(Decision)) != (2, 4, 4, 20):
        raise ValueError('unsupported ABI widths/layout')
    if [getattr(Decision, n).offset for n, _ in Decision._fields_] != [0, 4, 8, 12, 16]:
        raise ValueError('unsupported decision offsets')
    # Reject symlinks in every component and special filesystem paths.
    path = os.path.abspath(a.policy)
    current = '/'
    for part in path.split('/')[1:]:
        current = os.path.join(current, part)
        if stat.S_ISLNK(os.lstat(current).st_mode):
            raise ValueError('symlink policy path component')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= MAX_BYTES:
            raise ValueError('policy must be a nonempty regular file <=16MiB')
        data = f.read(MAX_BYTES + 1)
        if not 0 < len(data) <= MAX_BYTES:
            raise ValueError('policy read size outside bounds')
    version = subprocess.run(['dpkg-query', '-W', '-f=${Version}', 'libsepol2'],
                             check=True, capture_output=True, text=True, timeout=3).stdout
    lib = C.CDLL(LIB)
    libc = C.CDLL('libc.so.6')
    fmemopen = bind(libc, 'fmemopen', [C.c_void_p, C.c_size_t, C.c_char_p], C.c_void_p)
    fclose = bind(libc, 'fclose', [C.c_void_p])
    load = bind(lib, 'sepol_set_policydb_from_file', [C.c_void_p])
    context = bind(lib, 'sepol_context_to_sid', [C.c_char_p, C.c_size_t, C.POINTER(C.c_uint32)])
    klass = bind(lib, 'sepol_string_to_security_class', [C.c_char_p, C.POINTER(C.c_uint16)])
    perm = bind(lib, 'sepol_string_to_av_perm', [C.c_uint16, C.c_char_p, C.POINTER(C.c_uint32)])
    compute = bind(lib, 'sepol_compute_av_reason', [C.c_uint32, C.c_uint32, C.c_uint16,
                   C.c_uint32, C.POINTER(Decision), C.POINTER(C.c_uint)])
    minimum = bind(lib, 'sepol_policy_kern_vers_min', [])()
    maximum = bind(lib, 'sepol_policy_kern_vers_max', [])()
    if not 0 < minimum <= maximum:
        raise ValueError('invalid supported policy version range')
    buf = C.create_string_buffer(data)
    fp = fmemopen(buf, len(data), b'rb')
    if not fp:
        raise ValueError('fmemopen failed')
    try:
        checked(load(fp), 'parse supplied policy')
    finally:
        checked(fclose(fp), 'fclose')
    ssid, tsid, cls = C.c_uint32(), C.c_uint32(), C.c_uint16()
    checked(context(sc, len(sc) + 1, C.byref(ssid)), 'source context')
    checked(context(tc, len(tc) + 1, C.byref(tsid)), 'target context')
    checked(klass(cl, C.byref(cls)), 'class lookup')
    results = []
    for pname in perms:
        bit, decision, reason = C.c_uint32(), Decision(), C.c_uint()
        checked(perm(cls, pname, C.byref(bit)), 'permission lookup')
        if bit.value == 0 or bit.value & (bit.value - 1):
            raise ValueError('permission is not one bit')
        checked(compute(ssid, tsid, cls, bit, C.byref(decision), C.byref(reason)), 'compute AV')
        allowed = (decision.allowed & bit.value) == bit.value
        results.append({'permission': pname.decode(), 'bit': bit.value, 'allowed': allowed,
                        'denial_audit_bit_set': bool(decision.auditdeny & bit.value),
                        'denied_and_audit_suppressed': not allowed and not bool(decision.auditdeny & bit.value),
                        'reason_mask': reason.value,
                        'decision': {n: getattr(decision, n) for n, _ in Decision._fields_}})
    print(json.dumps({'scope': 'supplied saved policy only; no runtime context claim',
        'policy': path, 'policy_sha256': hashlib.sha256(data).hexdigest(), 'policy_bytes': len(data),
        'library': LIB, 'package_version': version, 'abi_source': SOURCE,
        'supported_policy_versions': [minimum, maximum], 'parse_succeeded': True,
        'query_assumptions': {'source_context': a.source_context, 'target_context': a.target_context,
                              'class': a.class_name}, 'results': results}, indent=2))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        sys.exit(1)
