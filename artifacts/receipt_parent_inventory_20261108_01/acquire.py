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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '06-tools'))
from guarded_adb_socket import GuardedADB

OUT = Path(__file__).resolve().parent
PRIVATE = Path.home() / '.cache/legion-y70-parent-inventory' / OUT.name
TRANSPORT_PIN = '375717914b1f230023ff02bec6fffe8dc79e73f53ee40f069a1dadcf85693aef'
MODULE = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
MUTEX = '/data/local/tmp/legion-pwm-research.lock'

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

def pins():
    check(hashlib.sha256((ROOT/'06-tools/guarded_adb_socket.py').read_bytes()).hexdigest() == TRANSPORT_PIN, 'Guarded transport pin changed')
    return {'acquisition_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'transport_sha256': TRANSPORT_PIN}

def main():
    sources = pins()
    if sys.argv[1:] == ['--check']:
        print(json.dumps({'offline_source_check': True, 'sources': sources}, sort_keys=True))
        return 0
    check(sys.argv[1:] == ['--execute'], 'Only --check or explicit --execute accepted')
    check(not (OUT/'result.json').exists() and not (OUT/'result.json').is_symlink()
          and not PRIVATE.exists() and not PRIVATE.is_symlink(), 'One-shot result/private path already exists')
    os.umask(0o077)
    PRIVATE.mkdir(parents=True, mode=0o700)
    report = {'started_at_utc': utc(), 'sources': sources, 'events': [], 'status': 'IN_PROGRESS',
              'device_files_written': False, 'device_files_planned': False, 'experimental_dsi': False, 'settings_changed': False,
              'all_failure_cleanup_proven': False, 'batch_or_candidate_admitted': False,
              'brightness_or_restore_measured': False, 'physical_pwm_hz': None}
    def save():
        (OUT/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    save()
    g = GuardedADB()
    def call(t, label, command, cap=4096):
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
            rc, out, err = bounded_shell(g, t, command, cap, partial=partial)
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
        return 'su -c ' + shlex.quote(command)
    try:
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
        pins()
        report['parents'] = {}
        for index,path in enumerate(('/data','/data/local','/data/local/tmp')):
            command = 'test -d '+shlex.quote(path)+' && test ! -L '+shlex.quote(path)+' && /system/bin/stat -c '+shlex.quote('%u %g %a %f')+' '+shlex.quote(path)
            data = read(target,'parent_'+str(index),root(command),cap=256)
            text = data.decode('ascii')
            check(re.fullmatch(r'[0-9]+ [0-9]+ [0-7]{3,4} [0-9a-f]+\n',text), 'Unexpected metadata grammar')
            uid,gid,mode,flags = text.split()
            check(int(flags,16)&0xf000==0x4000, 'Not a directory')
            report['parents'][path] = {'uid':int(uid),'gid':int(gid),'mode':mode,'directory_non_symlink':True}
        read(target,'shell_traverse_data_local','test -x /data/local',b'',16)
        candidate = report['parents']['/data/local']
        report['candidate_root_owned_non_group_or_other_writable'] = candidate['uid']==0 and (int(candidate['mode'],8)&0o022)==0
        report['shell_traverse_test_passed'] = True
        read(target,'boot_after','cat /proc/sys/kernel/random/boot_id',boot,64)
        read(target,'mutex_absent_after',root('test ! -e '+MUTEX+' && test ! -L '+MUTEX),b'',16)
        read(target,'enforcing_after','getenforce',b'Enforcing\n',16)
        report.update(boot_unchanged=True, mutex_absent_before_and_after=True, status='COMPLETED_LIMITED_OBSERVATION')
        return 0
    except BaseException as exc:
        report.update(status='STOPPED_REVIEW_REQUIRED', error_type=type(exc).__name__)
        return 2
    finally:
        report['finished_at_utc'] = utc()
        save()
        print(json.dumps({k:v for k,v in report.items() if k not in ('events','sources')},sort_keys=True))

if __name__ == '__main__':
    sys.exit(main())
