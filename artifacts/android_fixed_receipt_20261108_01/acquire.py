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
PRIVATE = Path.home() / '.cache/legion-y70-fixed-receipt' / OUT.name
PACKAGE = ROOT / '06-tools/android_fixed_receipt_probe'
PINSET = 'ff2e63976d1daf914b0164cb26807558451418d6bf09f1f41115e1104a264384'
TRANSPORT_PIN = '375717914b1f230023ff02bec6fffe8dc79e73f53ee40f069a1dadcf85693aef'
BASE = '/data/local/afr_synthetic_fixed_20261108_01'
SOURCE_SHA = '922bdfee53feef548d1b5509e682617dbaf49aa7c40e082bbe610b1b5f96d2a4'
MANIFEST = (b'scope=SYNTHETIC_ONLY\nepoch=synthetic_fixed_20261108_01\n'
            b'nonce=synthetic_fixed_nonce_01\nphase=SYNTHETIC_BINARY_01\n'
            b'source=' + SOURCE_SHA.encode() + b'\nstdout_bytes=2\nstderr_bytes=12\nexpected_rc=7\n')
PAYLOAD_OUT, PAYLOAD_ERR = b'\n\x00', b'diagnostic\n\x00'
COMMAND_CAP = 16384
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

def sha(data):
    return hashlib.sha256(data).hexdigest()

def pins():
    pinbytes = (PACKAGE/'SOURCE_PINS.sha256').read_bytes()
    check(sha(pinbytes) == PINSET, 'Reviewed package pinset changed')
    source = {}
    for row in pinbytes.decode('ascii').splitlines():
        digest, name = row.split('  ')
        check(re.fullmatch(r'[a-zA-Z0-9_.]+', name), 'Invalid package name')
        check(sha((PACKAGE/name).read_bytes()) == digest, 'Package source pin changed')
        source[name] = digest
    check(sha((ROOT/'06-tools/guarded_adb_socket.py').read_bytes()) == TRANSPORT_PIN, 'Transport source changed')
    return {'package': source, 'pinset_sha256': PINSET, 'transport_sha256': TRANSPORT_PIN,
            'acquisition_sha256': sha(Path(__file__).read_bytes())}

def command_limit(command):
    check(isinstance(command, str) and '\0' not in command, 'Invalid command')
    check(len(command.encode()) <= COMMAND_CAP, 'Command exceeds fixed dispatch cap')
    return command

def render(boot):
    check(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot), 'Invalid private boot')
    values = dict(BASE=BASE, PARENT='/data/local', ROOT_UID='0', SHELL_UID='2000',
                  PARENT_MODE='751', BOOT=boot, BOOT_FILE='/proc/sys/kernel/random/boot_id',
                  SH='/system/bin/sh', MANIFEST_SHA=sha(MANIFEST),
                  STDOUT_SHA=sha(PAYLOAD_OUT), STDERR_SHA=sha(PAYLOAD_ERR))
    result = {}
    for phase in ('reserve', 'capture', 'seal'):
        text = (PACKAGE/'common.sh.in').read_text() + (PACKAGE/(phase+'.sh.in')).read_text()
        for key, value in values.items():
            text = text.replace('@'+key+'@', value)
        check('@' not in text and text.count('PATH=/system/bin\n') == 1, 'Render mismatch')
        # All fixed script input is a single quoted -c argument, never interpolated by outer shell.
        command = shlex.join(['/system/bin/sh', '-c', text, 'fixed-receipt'])
        if phase != 'capture':
            # Seal's sole argument is appended later from the trusted actual capture rc.
            command = 'su -c ' + shlex.quote(command + (' 7' if phase == 'seal' else ''))
        result[phase] = (text.encode(), command_limit(command))
    return result

def expected_receipt(boot):
    return ('scope=SYNTHETIC_ONLY\nepoch=synthetic_fixed_20261108_01\nboot='+boot+
            '\nphase=SYNTHETIC_BINARY_01\nnonce=synthetic_fixed_nonce_01\nsource='+SOURCE_SHA+
            '\nmanifest='+sha(MANIFEST)+'\nactual_rc=7\nproducer_outcome=EXPECTED_NEGATIVE\nstdout=2:'+
            sha(PAYLOAD_OUT)+'\nstderr=12:'+sha(PAYLOAD_ERR)+'\nstructure=COMPLETE\n').encode()

class Sequence:
    """One instance, one attempt per phase. Failure permanently consumes host gate."""
    def __init__(self):
        self.next = 'reserve'
        self.actual_capture = None
    def access_gate(self, invoke):
        previous = self.next
        self.next = 'HOLD'
        check(previous == 'capture', 'Access gate requires accepted reserve')
        check(invoke() == b'', 'Access gate must be exact empty accepted read')
        self.next = 'capture'
    def run(self, phase, invoke):
        previous = self.next
        self.next = 'HOLD'
        check(previous == phase, 'Phase spent, failed, or out of order')
        if phase == 'seal':
            check(self.actual_capture == (7, b'', b''), 'No trusted capture status')
        result = invoke()
        expected = {'reserve': (0,b'RESERVED\n',b''), 'capture': (7,b'',b''),
                    'seal': (0,b'SEALED_EXPECTED_NEGATIVE\n',b'')}[phase]
        check(result == expected, 'Phase result nonconforming; retain HOLD')
        if phase == 'capture':
            self.actual_capture = result
        self.next = {'reserve':'capture','capture':'seal','seal':'audit'}[phase]
        return result

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
              'device_files_written': False, 'device_files_planned': True, 'experimental_dsi': False, 'settings_changed': False,
              'all_failure_cleanup_proven': False, 'batch_or_candidate_admitted': False,
              'brightness_or_restore_measured': False, 'physical_pwm_hz': None}
    def save():
        (OUT/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    save()
    report['device_file_plan'] = 'One fixed fresh root-owned directory retained as permanent spent marker; no cleanup'
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
        read(target,'root_gid',root('id -g'),b'0\n',16)
        read(target,'shell_gid','id -g',b'2000\n',16)
        read(target,'parent_access','test ! -w /data && test ! -w /data/local && test -x /data/local',b'',16)
        read(target,'parent_metadata',root("test ! -L /data && test ! -L /data/local && test ! -L /data/local/tmp && stat -c '%u:%g:%a' /data /data/local /data/local/tmp"),b'1000:1000:771\n0:0:751\n2000:2000:771\n',128)
        read(target,'fixed_base_fresh',root('test ! -e '+BASE+' && test ! -L '+BASE),b'',16)
        pins()
        rendered = render(boot.decode('ascii').rstrip('\n'))
        report['render_sha256'] = {}
        for phase, (script, command) in rendered.items():
            (PRIVATE/(phase+'.rendered.sh')).write_bytes(script)
            (PRIVATE/(phase+'.rendered.command')).write_text(command)
            report['render_sha256'][phase] = {'script':sha(script), 'command':sha(command.encode())}
        # All command lengths and actual boot-containing bytes are frozen privately BEFORE writes.
        (PRIVATE/'owned-context.json').write_text(json.dumps({'base':BASE,'boot':boot.decode(),
            'epoch':'synthetic_fixed_20261108_01','nonce':'synthetic_fixed_nonce_01'})+'\n')
        save()
        sequence = Sequence()
        report['device_file_creation_attempted'] = True
        report['device_files_written'] = None
        report['retained_owned_state'] = 'Reserve attempted; unknown completion retains HOLD, no cleanup/retry'
        save()
        for phase in ('reserve','capture','seal'):
            if phase == 'capture':
                # Actual Android DAC/SELinux access, not an inference from root stat modes.
                # Failure retains BASE and stops before producer or seal; no chmod/chcon fallback.
                sequence.access_gate(lambda: read(target,'shell_access_before_capture','test -x '+BASE+
                     ' && test -x '+BASE+'/source && test -x '+BASE+'/work && test -r '+BASE+
                     '/source/producer.sh && test -r '+BASE+'/source/manifest && test -w '+BASE+
                     '/work && test ! -r '+BASE+'/control && test ! -w '+BASE+'/control',b'',16))
                report['shell_access_before_capture_passed'] = True
            sequence.run(phase, lambda phase=phase: call(target,phase,rendered[phase][1],128))
            report[phase+'_accepted'] = True
            if phase == 'reserve':
                report['device_files_written'] = True
            save()
        def audit_file(label, relative, expected, uid, gid, mode):
            path = BASE+'/'+relative
            q = shlex.quote(path)
            metadata = f'{uid}:{gid}:{mode}:1:{len(expected)}\n'.encode()
            read(target,label+'_metadata',root('test -f '+q+' && test ! -L '+q+" && stat -c '%u:%g:%a:%h:%s' "+q),metadata,128)
            read(target,label+'_bytes',root('cat '+q),expected,len(expected)+16)
        def audit_dir(label, relative, uid, gid, mode):
            q = shlex.quote(BASE+('/'+relative if relative else ''))
            read(target,label,root('test -d '+q+' && test ! -L '+q+" && stat -c '%u:%g:%a' "+q),f'{uid}:{gid}:{mode}\n'.encode(),64)
        for label,rel,uid,gid,mode in [('audit_base','',0,0,711),('audit_control','control',0,0,700),
                ('audit_source','source',0,0,755),('audit_work','work',0,0,700),
                ('audit_dispatched','work/dispatched',2000,2000,700),
                ('audit_seal_attempt','control/seal_attempt',0,0,700),('audit_sealing','control/sealing',0,0,700)]:
            audit_dir(label,rel,uid,gid,mode)
        for label,rel,data,uid,gid,mode in [
                ('audit_complete','control/complete',b'COMPLETE\n',0,0,400),
                ('audit_receipt','control/receipt',expected_receipt(boot.decode().rstrip('\n')),0,0,400),
                ('audit_producer','source/producer.sh',(PACKAGE/'producer.sh').read_bytes(),0,0,444),
                ('audit_manifest','source/manifest',MANIFEST,0,0,444),
                ('audit_stdout','control/stdout',PAYLOAD_OUT,0,0,400),
                ('audit_stderr','control/stderr',PAYLOAD_ERR,0,0,400),
                ('audit_state','control/state',b'RESERVED\n',0,0,600),
                ('audit_work_stdout','work/stdout',PAYLOAD_OUT,2000,2000,600),
                ('audit_work_stderr','work/stderr',PAYLOAD_ERR,2000,2000,600)]:
            audit_file(label,rel,data,uid,gid,mode)
        read(target,'shell_isolation','test ! -r '+BASE+'/control/receipt && test ! -w '+BASE+
             '/control/receipt && test ! -r '+BASE+'/control && test ! -w '+BASE+
             '/control && test ! -w '+BASE+'/source/producer.sh && test ! -w '+BASE+'/source/manifest',b'',16)
        report.update(independent_audit_passed=True, actual_capture_rc=sequence.actual_capture[0],
                      producer_outcome='EXPECTED_NEGATIVE', shell_isolation_observed=True,
                      retained_owned_state='Fixed root BASE spent marker, source, work, control and receipt retained; no cleanup')
        read(target,'boot_after','cat /proc/sys/kernel/random/boot_id',boot,64)
        read(target,'mutex_absent_after',root('test ! -e '+MUTEX+' && test ! -L '+MUTEX),b'',16)
        read(target,'enforcing_after','getenforce',b'Enforcing\n',16)
        report.update(boot_unchanged=True, mutex_absent_before_and_after=True, status='COMPLETED_SYNTHETIC_EXPECTED_NEGATIVE')
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
