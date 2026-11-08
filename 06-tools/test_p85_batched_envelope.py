"""Offline framing and real-host-shell envelope tests. No ADB or devices."""
from dataclasses import replace
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import time
import unittest

import p85_batched_envelope as e

N='aabbccddeeff'


def framed(plan,payloads):
    prefix=('@P85E:'+plan.nonce+':').encode();out=prefix+b'START\n'
    for part in plan.parts:
        payload=payloads[part.label]
        if isinstance(payload,str):payload=payload.encode()
        out+=prefix+f'SECTION {part.label} 0 {len(payload)} 0\n'.encode()+payload+b'\n'+prefix+b'END '+part.label.encode()+b'\n'
    return out+prefix+b'DONE\n'


def local_script(plan,root):
    bin=root/'bin';bin.mkdir(exist_ok=True)
    for name,text in {
        'id':'#!/bin/sh\necho 2000\n',
        'su':'#!/bin/sh\n[ "$1" = -c ] || exit 90\nexec /bin/sh -c "$2"\n',
        'stat':'#!/bin/sh\nif [ "$1" = -c ] && [ "$2" = %u ]; then echo 2000; else exec /usr/bin/stat "$@"; fi\n',
    }.items():
        path=bin/name;path.write_text(text);path.chmod(0o700)
    work=root/'owned'
    command=e.script(plan).replace('/system/bin/sh','/bin/sh').replace(plan.work,str(work))
    environ={**os.environ,'PATH':str(bin)+':/usr/bin:/bin'}
    return command,environ,work


class EnvelopeTests(unittest.TestCase):
    def plan(self):return e.Envelope(N,(e.Part('ONE','/usr/bin/printf hello'),e.Part('TWO','/usr/bin/printf world',True)),10)

    def test_roundtrip_and_actual_privilege_wrappers(self):
        plan=self.plan()
        with tempfile.TemporaryDirectory() as directory:
            command,environ,work=local_script(plan,Path(directory))
            result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(e.parse(result.stdout,plan,returncode=result.returncode,stderr=result.stderr),{'ONE':'hello','TWO':'world'})
            self.assertFalse(work.exists())
        self.assertIn("su -c",e.script(plan))
        state=e.state_envelope(N,'set -eu; true')
        self.assertEqual([(p.label,p.root) for p in state.parts],[('FIELDS',True),('DISPLAY',False),('BOOT',False),('OWNER',True)])

    def test_padded_wc_counts_are_normalized_without_payload_changes(self):
        plan=self.plan()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);command,environ,work=local_script(plan,root)
            wc=root/'bin/wc'
            wc.write_text('#!/bin/sh\nn=$(/usr/bin/wc "$@"); printf "  %9d\\n" "$n"\n');wc.chmod(0o700)
            result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(e.parse(result.stdout,plan),{'ONE':'hello','TWO':'world'})
            self.assertFalse(work.exists())

    def test_missing_duplicate_reorder_embedded_truncation_and_trailing(self):
        plan=self.plan();raw=framed(plan,{'ONE':b'hello','TWO':b'world'})
        prefix=('@P85E:'+N+':').encode()
        bad=[raw[1:],raw[:-1],raw+b'extra',raw.replace(prefix+b'START\n',prefix+b'START\n'+prefix+b'START\n'),
             raw.replace(b'SECTION ONE',b'SECTION TWO',1),raw.replace(b'END ONE',b'END TWO',1),
             raw.replace(b' 0 5 0\n',b' 0 6 0\n',1),raw.replace(prefix+b'END ONE\n',b'',1),
             framed(plan,{'ONE':prefix+b'DONE\n','TWO':b'world'})]
        for item in bad:
            with self.subTest(length=len(item)),self.assertRaises(ValueError):e.parse(item,plan)
        for offset in range(len(raw)):
            with self.assertRaises(ValueError):e.parse(raw[:offset],plan)

    def test_invalid_utf8_nul_sizes_status_and_stderr(self):
        plan=self.plan()
        for payload in (b'\xff',b'\x00',b'x'*1025):
            with self.assertRaises(ValueError):e.parse(framed(plan,{'ONE':payload,'TWO':b''}),plan)
        raw=framed(plan,{'ONE':b'hello','TWO':b'world'})
        for bad in (raw.replace(b'SECTION ONE 0',b'SECTION ONE 7'),raw.replace(b' 0 5 0',b' 0 5 1')):
            with self.assertRaises(ValueError):e.parse(bad,plan)
        with self.assertRaises(ValueError):e.parse(raw,plan,returncode=1)
        with self.assertRaises(ValueError):e.parse(raw,plan,stderr=b'warning')
        with self.assertRaises(ValueError):e.parse(b'x'*(e.MAX_TOTAL+1),plan)

    def test_every_component_nonzero_or_stderr_stops_next_command(self):
        for index in range(3):
            for failure in ('exit 17','/usr/bin/printf warning >&2'):
                with self.subTest(index=index,failure=failure),tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);attempts=root/'attempts'
                    parts=[]
                    for i in range(3):
                        command=f'echo {i} >> {shlex.quote(str(attempts))}; '+(failure if i==index else 'true')
                        parts.append(e.Part('P'+str(i),command))
                    plan=e.Envelope(N,tuple(parts),10)
                    command,environ,work=local_script(plan,root)
                    result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
                    self.assertEqual(result.returncode,17 if failure=='exit 17' else 75)
                    self.assertEqual(attempts.read_text().splitlines(),[str(i) for i in range(index+1)])
                    self.assertFalse(work.exists())
                    with self.assertRaises(ValueError):e.parse(result.stdout,plan,returncode=result.returncode,stderr=result.stderr)

    def test_oversize_and_large_external_printf_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);large=root/'log';large.write_bytes(b'retained native log\n'*150000)
            plan=e.Envelope(N,(e.Part('KERNEL','cat '+str(large),True,4*1024*1024),),10)
            command,environ,work=local_script(plan,root)
            result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(e.parse(result.stdout,plan)['KERNEL'].encode(),large.read_bytes())
            self.assertFalse(work.exists())
            small=replace(plan,parts=(replace(plan.parts[0],limit=1024),))
            command,environ,work=local_script(small,root)
            result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
            self.assertEqual(result.returncode,74);self.assertFalse(work.exists())

    def test_unchanged_child_bytes_and_exactly_one_child(self):
        for kind in ('p85','c1','sham15','return15'):
            plan=e.child_envelope(N,'set -eu; true','parent_token',kind,'MARKER_BEGIN','MARKER_END','/data/local/tmp/p85_test')
            expected=(e.p85.long3_reader(N,'parent_token') if kind=='p85' else
                      e.p85.bounded_c1_reader(N,'parent_token') if kind=='c1' else e.p85.write_script(N,'parent_token',kind))
            self.assertEqual(plan.child_command,expected)
            self.assertEqual([p.command for p in plan.parts if p.label=='CHILD'],[expected])
            body=shlex.split(e.script(plan))[-1]
            part=next(part for part in plan.parts if part.label=='CHILD')
            childline='part CHILD '+str(part.limit)+' '+str(part.seconds)+' '+shlex.quote('su -c '+shlex.quote(expected))+'\n'
            self.assertEqual(body.count(childline),1)
            self.assertEqual(subprocess.run(['sh','-n'],input=e.script(plan),text=True,capture_output=True).returncode,0)
        with self.assertRaises(ValueError):e.child_envelope(N,'true','parent_token','candidate14','MARKER_BEGIN','MARKER_END','/data/local/tmp/p85_test')

    def test_state_checks(self):
        state={'FIELDS':'6438\n0\n0\nEnforcing\n','DISPLAY':'mActiveSfDisplayMode= peakRefreshRate=120.00001',
               'BOOT':'boot-id\n','OWNER':''}
        self.assertTrue(e.validate_state(state,6438,'boot-id'))
        for key,value in (('FIELDS','3600\n0\n0\nEnforcing'),('DISPLAY','mActiveSfDisplayMode= peakRefreshRate=90'),('BOOT','wrong'),('OWNER','noise')):
            with self.assertRaises(ValueError):e.validate_state({**state,key:value},6438,'boot-id')

    def test_owned_cleanup_refuses_collision_symlink_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=self.plan();command,environ,work=local_script(plan,root)
            work.mkdir(mode=0o700);(work/'unrelated').write_text('keep')
            result=subprocess.run(['sh','-c',command],capture_output=True,env=environ,timeout=15)
            self.assertNotEqual(result.returncode,0);self.assertTrue((work/'unrelated').exists())
            cleanup=e.remnant_cleanup(plan.work,plan.owner_digest).replace(plan.work,str(work))
            result=subprocess.run(['sh','-c',cleanup],capture_output=True,env=environ,timeout=5)
            self.assertNotEqual(result.returncode,0);self.assertTrue((work/'unrelated').exists())
            (work/'owner').write_text(N+':'+plan.owner_digest);(work/'owner').chmod(0o600)
            (work/'stdout').write_text('owned');(work/'stderr').write_text('owned')
            result=subprocess.run(['sh','-c',cleanup],capture_output=True,env=environ,timeout=5)
            self.assertNotEqual(result.returncode,0)  # Unknown file deliberately prevents rmdir.
            self.assertTrue((work/'unrelated').exists());self.assertFalse((work/'stdout').exists())
            (work/'unrelated').unlink();work.rmdir();work.symlink_to(root/'bin')
            result=subprocess.run(['sh','-c',cleanup],capture_output=True,env=environ,timeout=5)
            self.assertNotEqual(result.returncode,0);self.assertTrue(work.is_symlink())

    def test_signal_timeout_and_hardkill_never_launch_next_child(self):
        # Bounded surrogate foreground child, not Android DSI. Hard kill cannot
        # guarantee instantaneous cancellation; its OWN timeout still bounds it.
        for signum in (None,signal.SIGHUP,signal.SIGTERM,signal.SIGKILL):
            with self.subTest(signum=signum),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);started=root/'started';forbidden=root/'forbidden'
                inner=f'echo started > {started}; sleep 10; echo BAD > {forbidden}'
                child='timeout -k .1 .3 sh -c '+shlex.quote(inner)
                plan=e.Envelope(N,(e.Part('CHILD',child,False,1024,2),e.Part('NEXT','echo BAD > '+str(forbidden))),4)
                # For this cancellation fixture no root child assertion is needed.
                plan=replace(plan,parts=(replace(plan.parts[0],label='FIRST'),plan.parts[1]))
                command,environ,work=local_script(plan,root)
                process=subprocess.Popen(['sh','-c',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environ)
                deadline=time.monotonic()+2
                while not started.exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(started.exists())
                if signum:process.send_signal(signum)
                stdout,stderr=process.communicate(timeout=6)
                self.assertNotEqual(process.returncode,0)
                time.sleep(.4)
                self.assertFalse(forbidden.exists())
                with self.assertRaises(ValueError):e.parse(stdout,plan,returncode=process.returncode,stderr=stderr)
                # Any leftover is only the known workdir; recovery path owns cleanup.
                if work.exists():
                    cleanup=e.remnant_cleanup(plan.work,plan.owner_digest).replace(plan.work,str(work))
                    result=subprocess.run(['sh','-c',cleanup],capture_output=True,env=environ,timeout=5)
                    self.assertEqual(result.returncode,0,result.stderr)


    def test_host_hardkill_before_or_after_dispatched_child_is_uncertain_and_bounded(self):
        # Killing the host-side waiter does NOT prove an authorized remote child
        # did not run. At most that one bounded child may run; no next DSI exists.
        for when in ('before','after'):
            with self.subTest(when=when),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);ready=root/'ready';count=root/'child-count';bad=root/'bad'
                child='timeout -k .1 .3 sh -c '+shlex.quote(f'echo one >> {count}; sleep 10; echo BAD > {bad}')
                if when=='before':
                    parts=(e.Part('WAIT',f'echo ready > {ready}; sleep .3'),e.Part('FIRST',child,False,1024,2))
                else:
                    parts=(e.Part('FIRST',f'echo one >> {count}'),e.Part('WAIT',f'echo ready > {ready}; sleep .3'))
                plan=e.Envelope(N,parts,4)
                command,environ,work=local_script(plan,root)
                process=subprocess.Popen(['sh','-c',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environ)
                deadline=time.monotonic()+2
                while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(ready.exists());process.kill()
                stdout,stderr=process.communicate(timeout=6)
                self.assertNotEqual(process.returncode,0)
                self.assertFalse(bad.exists())
                self.assertLessEqual(len(count.read_text().splitlines()) if count.exists() else 0,1)
                with self.assertRaises(ValueError):e.parse(stdout,plan,returncode=process.returncode,stderr=stderr)
                if work.exists():
                    cleanup=e.remnant_cleanup(plan.work,plan.owner_digest).replace(plan.work,str(work))
                    result=subprocess.run(['sh','-c',cleanup],capture_output=True,env=environ,timeout=5)
                    self.assertEqual(result.returncode,0,result.stderr)


class CommandSizeTests(unittest.TestCase):
    def test_maximum_inputs_fit_and_oversize_rejected(self):
        sizes=e.size_preflight()
        self.assertEqual(set(sizes),{'state','quiet','hold_end','p85','c1','sham15','return15'})
        for value in sizes.values():
            self.assertLessEqual(value['service_bytes'],65535)
            self.assertLessEqual(value['shell_argv_bytes_including_nul'],131072)
        with self.assertRaises(ValueError):e.command_sizes('x'*65524)
        with self.assertRaises(ValueError):e.command_sizes('я'*32768)


if __name__=='__main__':unittest.main()
