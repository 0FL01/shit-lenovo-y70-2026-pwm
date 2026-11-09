#!/usr/bin/env python3
"""Fixed one-shot acquisition; default checks sources without any transport I/O."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import sys
import time

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from guarded_adb_socket import GuardedADB

OUT = Path(__file__).resolve().parent
PRIVATE = Path.home() / '.cache/legion-y70-loaded-policy' / OUT.name
TRANSPORT_PIN = '375717914b1f230023ff02bec6fffe8dc79e73f53ee40f069a1dadcf85693aef'
MODULE = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
MUTEX = '/data/local/tmp/legion-pwm-research.lock'
POLICY_CAP = 16 * 1024 * 1024
POLICY_PATH = '/sys/fs/selinux/policy'
COMMAND_CAP = 4096

def check(value, message):
    if not value:
        raise RuntimeError(message)

def utc():
    return datetime.now(timezone.utc).isoformat()

def bounded_shell(g, transport, command, cap=4096, timeout=8, partial=None):
    """Limit shell-v2 bytes before frame read/accumulation; not cancellation."""
    out, err = bytearray(), bytearray()
    deadline = time.monotonic() + timeout
    try:
        with g.selected(transport, 'shell,v2,raw:' + command, timeout) as sock:
            def exact(count):
                data = bytearray()
                while len(data) < count:
                    remaining = deadline - time.monotonic()
                    check(remaining > 0, 'Host acceptance deadline expired; remote outcome unknown')
                    sock.settimeout(remaining)
                    part = sock.recv(count-len(data))
                    check(time.monotonic() < deadline, 'Late bytes; remote outcome unknown')
                    check(bool(part), 'Transport closed; remote outcome unknown')
                    data.extend(part)
                return bytes(data)
            while True:
                channel, size = struct.unpack('<BI', exact(5))
                if channel in (1, 2):
                    check(size <= cap - len(out) - len(err), 'Response byte cap exceeded; remote outcome unknown')
                    data = exact(size)
                    (out if channel == 1 else err).extend(data)
                elif channel == 3:
                    check(size == 1, 'Invalid exit frame')
                    rc = exact(1)[0]
                    check(time.monotonic() < deadline, 'Late exit; remote outcome unknown')
                    return rc, bytes(out), bytes(err)
                else:
                    raise RuntimeError('Unexpected shell-v2 channel')
    finally:
        # Incomplete current-frame bytes are not returned as an accepted stream.
        if partial is not None:
            partial(bytes(out), bytes(err))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def pins():
    digest = sha((ROOT/'06-tools/guarded_adb_socket.py').read_bytes())
    check(digest == TRANSPORT_PIN, 'Guarded transport source changed')
    return {'transport_sha256': digest, 'acquisition_sha256': sha(Path(__file__).read_bytes())}

def command_limit(command):
    check(isinstance(command, str) and '\0' not in command, 'Invalid command')
    check(len(command.encode()) <= COMMAND_CAP, 'Command exceeds fixed dispatch cap')
    return command

def validate_policy_header(policy, size):
    check(bool(policy), 'Empty policy snapshot')
    check(size == 0 or len(policy) == size, 'Policy length differs from advertised size')
    # Linux binary policy magic and bounded header identity, not full validation.
    check(len(policy) >= 12 and struct.unpack('<I',policy[:4])[0] == 0xf97cff8c, 'Unsupported/truncated binary policy header')
    ident_len = struct.unpack('<I',policy[4:8])[0]
    check(ident_len == 8 and policy[8:16] == b'SE Linux', 'Unsupported policy identity')
    check(len(policy) >= 24, 'Truncated policy header')
    policy_version = struct.unpack('<I',policy[16:20])[0]
    check(15 <= policy_version <= 40, 'Unsupported policy version')
    return policy_version

def parse_context(raw):
    # Saved kernel getprocattr returns the context length including one NUL.
    check(raw.endswith(b'\0') and raw.count(b'\0') == 1, 'Expected single terminal context NUL')
    body = raw[:-1]
    check(re.fullmatch(rb'u:r:[a-zA-Z0-9_]+:s[0-9]+(?::c[0-9]+(?:[.,]c?[0-9]+)*)?',body), 'Unexpected context syntax')
    return body.decode('ascii')

def main():
    sources = pins()
    if sys.argv[1:] in ([], ['--check']):
        print(json.dumps({'offline_source_check': True, 'sources': sources}, sort_keys=True))
        return 0
    check(sys.argv[1:] == ['--execute'], 'Only --check or explicit --execute accepted')
    check(not (OUT/'result.json').exists() and not (OUT/'result.json').is_symlink()
          and not PRIVATE.exists() and not PRIVATE.is_symlink(), 'One-shot result/private path already exists')
    os.umask(0o077)
    PRIVATE.mkdir(parents=True, mode=0o700)
    report = {'started_at_utc': utc(), 'sources': sources, 'events': [], 'status': 'IN_PROGRESS',
              'device_files_written': False, 'device_files_planned': False, 'experimental_dsi': False, 'settings_changed': False,
              'no_device_mutations_planned': True, 'remote_cancellation_proven': False, 'batch_or_candidate_admitted': False,
              'brightness_or_restore_measured': False, 'physical_pwm_hz': None}
    def save():
        (OUT/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    save()
    report['device_file_plan'] = 'Read-only loaded SELinux policy snapshot; no device writes'
    def call(t, label, command, cap=4096):
        command_limit(command)
        event = {'label': label, 'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
                 'started_at_utc': utc(), 'cap_bytes': cap, 'transport_complete': False}
        report['events'].append(event)
        (PRIVATE/(label+'.command.txt')).write_text(command)
        save()
        started = time.monotonic()
        try:
            def partial(out, err):
                (PRIVATE/(label+'.partial.stdout')).write_bytes(out)
                (PRIVATE/(label+'.partial.stderr')).write_bytes(err)
                event['partial_streams_complete_frames_only'] = True
            rc, out, err = bounded_shell(g, t, command, cap, timeout=30 if label == 'loaded_policy' else 8, partial=partial)
            (PRIVATE/(label+'.stdout')).write_bytes(out)
            (PRIVATE/(label+'.stderr')).write_bytes(err)
            event.update(rc=rc, stdout_bytes=len(out), stderr_bytes=len(err), transport_complete=True)
            (PRIVATE/(label+'.event.json')).write_text(json.dumps(event, sort_keys=True)+'\n')
            return rc, out, err
        except BaseException as exc:
            event['error_type'] = type(exc).__name__
            raise
        finally:
            event['elapsed_seconds'] = time.monotonic()-started
            event['finished_at_utc'] = utc()
            (PRIVATE/(label+'.event.json')).write_text(json.dumps(event, sort_keys=True)+'\n')
            save()
    def read(t, label, command, expected=None, cap=4096):
        rc, out, err = call(t, label, command, cap)
        check(rc == 0 and not err, 'Read-only prerequisite failed')
        if expected is not None:
            check(out == expected, 'Read-only prerequisite mismatch')
        return out
    def root(command):
        return 'su -c ' + shlex.quote('PATH=/system/bin; LC_ALL=C; export PATH LC_ALL; '+command)
    try:
        g = GuardedADB()
        g.preflight()
        report['existing_server_version_preflight'] = True
        rows = [x.split() for x in g.host('host:devices-l').decode('ascii').splitlines()]
        def select(device):
            hits = [r for r in rows if len(r)>2 and r[1]=='device' and 'device:'+device in r]
            check(len(hits)==1, 'Target/camera selection is not unique')
            ids = [x.split(':',1)[1] for x in hits[0] if x.startswith('transport_id:')]
            check(len(ids)==1 and re.fullmatch(r'[1-9][0-9]*',ids[0]), 'Invalid transport ID')
            t = int(ids[0]); g.bind(t); return t
        target, camera = select('avr'), select('Galaga')
        check(g.identities[str(target)] != g.identities[str(camera)], 'Target and camera collide')
        report['fresh_distinct_immutable_bindings'] = True
        read(camera,'camera_identity','getprop ro.product.device; getprop ro.boot.hardware.sku; getprop ro.product.model',b'Galaga\nROW\nA001\n',256)
        read(target,'target_identity','getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce; getprop ro.product.device',b'XT2611-1\nW3WWS36.65-64-4-1\n_b\n6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k\nEnforcing\navr\n',1024)
        read(target,'root_identity',root('id -u'),b'0\n',16)
        read(target,'panel_identity',root('cat /sys/class/drm/card0-DSI-1/panelName'),b'boe_ili97701A_682_1440x3168_dsc_cmd_v4\n',128)
        read(target,'module_identity',root('sha256sum /vendor/lib/modules/msm_drm.ko'),(MODULE+'  /vendor/lib/modules/msm_drm.ko\n').encode(),256)
        read(target,'mutex_absent_before',root('test ! -e '+MUTEX+' && test ! -L '+MUTEX),b'',16)
        boot = read(target,'boot_before','cat /proc/sys/kernel/random/boot_id',cap=64)
        check(re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\n',boot), 'Invalid boot identity')
        read(target,'shell_uid','id -u',b'2000\n',16)
        report['identity_guards_passed'] = True
        # Context belongs to this fresh plain-shell observation, not an earlier process.
        context = read(target,'fresh_shell_context','cat /proc/$$/attr/current; rc=$?; exit "$rc"',cap=256)
        report['fresh_plain_shell_context'] = parse_context(context)
        policy_stat = read(target,'policy_size_before',root("stat -c '%s' "+POLICY_PATH),cap=64)
        check(re.fullmatch(rb'[0-9]+\n', policy_stat), 'Unsupported policy size metadata')
        size = int(policy_stat)
        check(0 <= size <= POLICY_CAP, 'Policy size exceeds cap')
        # selinuxfs may expose size0 before opening a generated policy file. It is
        # not an empty-policy claim; complete bounded read and parser qualification
        # are still mandatory. Nonzero advertised size must match exactly.
        report['policy_stat_size_before'] = size
        report['policy_stat_size_meaningful'] = size > 0
        pins()
        policy = read(target,'loaded_policy',root('cat '+POLICY_PATH),cap=POLICY_CAP)
        policy_version = validate_policy_header(policy,size)
        # Exact file bytes are private; structural completeness needs the separately
        # qualified libsepol parser. This snapshot does not claim parse validity.
        (PRIVATE/'loaded-policy.bin').write_bytes(policy)
        policy_hash = sha(policy)
        # Independent read hashes current source; mismatch stops without retry.
        read(target,'policy_hash_after',root('sha256sum '+POLICY_PATH),
             (policy_hash+'  '+POLICY_PATH+'\n').encode(),256)
        policy_size_after = read(target,'policy_size_after',root("stat -c '%s' "+POLICY_PATH),cap=64)
        check(policy_size_after == policy_stat, 'Policy metadata changed across snapshot')
        read(target,'boot_after','cat /proc/sys/kernel/random/boot_id',boot,64)
        read(target,'mutex_absent_after',root('test ! -e '+MUTEX+' && test ! -L '+MUTEX),b'',16)
        read(target,'enforcing_after','getenforce',b'Enforcing\n',16)
        report.update(policy_bytes=len(policy), policy_sha256=policy_hash, policy_version=policy_version,
                      loaded_policy_source_verified=True, source_hash_after_matches=True,
                      boot_unchanged=True, mutex_absent_before_and_after=True,
                      full_policy_parser_validation=False,
                      context_is_fresh_not_historical=True,
                      policy_change_history_proven=False,
                      status='SNAPSHOT_CAPTURED_PENDING_OFFLINE_PARSE')
        return 0
    except BaseException as exc:
        report.update(status='HOLD_REVIEW_REQUIRED', error_type=type(exc).__name__)
        (PRIVATE/'failure.txt').write_text(str(exc)+'\n')
        return 2
    finally:
        report['finished_at_utc'] = utc()
        save()
        print(json.dumps({k:v for k,v in report.items() if k not in ('events','sources')},sort_keys=True))

if __name__ == '__main__':
    sys.exit(main())
