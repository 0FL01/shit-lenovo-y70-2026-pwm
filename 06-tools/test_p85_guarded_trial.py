"""OFFLINE: real generated shell in fake files, never ADB/device operations."""
from dataclasses import replace
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import p85_guarded_trial as p
import stock_c1_sweep as stock
from test_stock_c1_sweep import execute_reader_fixture

N='aabbccddeeff'


def writer_fixture(stage='candidate14', mode='normal', *, retained_bytes=0, external_printf=False, legacy_kernel_argv=False):
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for name in ('C','T','T/events/pwm_c1_'+N,'W','W/dbg','sys/kernel/tracing','bl'):
            (root/name).mkdir(parents=True,exist_ok=True)
        line='[12345.678] dsi-ctrl-1: dsi_ctrl_cmd_transfer len=4, type=0x39 hs cmds= ff 5a a5 00\n'
        (root/'retained.log').write_text(line*((retained_bytes+len(line)-1)//len(line)))
        (root/'T/trace').write_text(''); (root/'T/tracing_on').write_text('0')
        (root/'bl/brightness').write_text('3600'); (root/'bl/bl_power').write_text('0')
        (root/'esd').write_text('reg_read\n')
        names=('header','hardware','ctrl','tx','entry')
        (root/'sys/kernel/tracing/kprobe_profile').write_text(''.join(f'{x}_{N} 0 0\n' for x in names))
        body=shlex.split(p.write_script(N,'parent_token',stage))[8]
        if legacy_kernel_argv:
            body=body.replace(' dmesg > "$W/gate-kernel" || return 43',
                ' kernel=$(dmesg) || return 43\n /usr/bin/printf \'%s\\n\' "$kernel" > "$W/gate-kernel" || return 43')
        functions=body[body.index("previous_count=0"):body.index('trap cleanup EXIT')]
        tail=body[body.index('touched=1\n'):]
        mock=r'''
umount() { return 0; }
rmdir() { return 0; }
getenforce() { echo Enforcing; }
dmesg() {
 cat "$ROOT/retained.log"
 if [ "$MODE" = dmesg-fail ]; then return 1; fi
 command printf 'PWM_P85_WRITE_NONCE_BEGIN\n'
 n=1
 while [ "$n" -le "$dsi" ]; do
  case "$n" in
   1) payload='ff 5a a5 23'; length=4;;
   2) payload='85 VALUE'; length=2;;
   3) payload='ff 5a a5 00'; length=4;;
  esac
  if [ "$MODE" = "bad-wire-$n" ]; then payload='00 00'; fi
  command printf 'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=%s, type=0x39 hs cmds= %s\n' "$length" "$payload"
  n=$((n+1))
 done
 if [ "$MODE" = extra-wire ] && [ "$dsi" = 1 ]; then command printf 'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= 51 00\n'; fi
}
row() { command printf ' printf-%s [004] d... 12345.1: %s_NONCE: %s\n' "$3" "$1" "$2" >> "$T/trace"; }
profiles() {
 : > "$ROOT/sys/kernel/tracing/kprobe_profile"
 for name in header hardware ctrl tx entry; do
  count=$(awk -v name="${name}_NONCE:" 'index($0,name) {n++} END {print n+0}' "$T/trace")
  miss=0; if [ "$MODE" = misses ] && [ "$dsi" = 2 ] && [ "$name" = entry ]; then miss=1; fi
  command printf '%s_NONCE %s %s\n' "$name" "$count" "$miss" >> "$ROOT/sys/kernel/tracing/kprobe_profile"
 done
}
printf() {
 case "${2-}" in
  reg_read)
   if [ "$MODE" = esd-after-freeze ]; then
    [ "$(cat "$T/events/$G/enable")" = 0 ] || return 52
    grep -Fq -- "-:$G/header_NONCE" "$ROOT/sys/kernel/tracing/kprobe_events" || return 53
    command printf 'header_NONCE 99 0\n' > "$ROOT/sys/kernel/tracing/kprobe_profile"
   fi
  ;;
  '0x39 '*)
   dsi=$((dsi+1)); command printf '%s\n' "$2" >> "$ROOT/attempts"
   if [ "$MODE" = "shell-fail-$dsi" ]; then return 1; fi
   rc=0; if [ "$MODE" = "native-fail-$dsi" ]; then rc=-5; fi
   length=11; if [ "$dsi" = 2 ]; then length=9; fi
   flags=0; pending=0
   if [ "$MODE" = pending ] && [ "$dsi" = 1 ]; then pending=11; fi
   if [ "$MODE" = flags ] && [ "$dsi" = 1 ]; then flags=64; fi
   pid=$((100+dsi)); row entry "pending=$pending length=$length flags=$flags" "$pid"
   row ctrl "rc=$rc" "$pid"; row tx "rc=$rc" "$pid"; profiles
   if [ "$MODE" = corrupt-prefix ] && [ "$dsi" = 2 ]; then sed -i '1s/12345.1/12345.2/' "$T/trace"; fi
   if [ "$MODE" = signal-term ] && [ "$dsi" = 2 ]; then kill -TERM $$; fi
   if [ "$MODE" = signal-hup ] && [ "$dsi" = 2 ]; then kill -HUP $$; fi
  ;;
 esac
 command printf "$@"
}
'''.replace('NONCE',N).replace('VALUE','14' if stage=='candidate14' else '15')
        setup=(f'set -eu\nROOT={shlex.quote(str(root))}\nMODE={shlex.quote(mode)}\n'
               f'C="$ROOT/C"; E="$ROOT/esd"; T="$ROOT/T"; W="$ROOT/W"; G=pwm_c1_{N}\n'
               'mounted=1; touched=0; traced=1; made_work=1; owned=0; dsi=0\n'
               "added='"+' '.join(x+'_'+N for x in names)+"'\n")
        script=setup+mock+functions+"trap cleanup EXIT\ntrap 'exit 30' HUP INT TERM\n"+"command printf 'STATE 3600 120.00001\\nESD_INITIAL reg_read\\n'\n"+tail
        script=script.replace('/sys/kernel/tracing/',str(root/'sys/kernel/tracing')+'/')
        script=script.replace('$ROOT'+str(root/'sys/kernel/tracing'),'$ROOT/sys/kernel/tracing')
        script=script.replace('/dev/kmsg',str(root/'kmsg')).replace(stock.BL,str(root/'bl')+'/')
        if external_printf:script=script.replace('command printf','/usr/bin/printf')
        result=subprocess.run(['sh'],input=script,text=True,capture_output=True,timeout=10)
        attempts=(root/'attempts').read_text().splitlines() if (root/'attempts').exists() else []
        if any((root/'W'/name).exists() for name in p.WRITER_GATE_FILES):
            raise AssertionError('Owned gate snapshots leaked after shell cleanup')
        return result,attempts,(root/'esd').read_text().strip()


class TrialTests(unittest.TestCase):
    def test_writer_three_callbacks_and_no_cleanup_dsi(self):
        for stage in ('sham15','candidate14','return15'):
            result,attempts,esd=writer_fixture(stage)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            packets=[bytes(int(x,16) for x in line.split()) for line in attempts]
            self.assertEqual(tuple(packets),p.proposal('candidate14' if stage=='candidate14' else 'restore15'))
            self.assertEqual(esd,'reg_read')
            self.assertEqual(result.stdout.count('WRITE_GATE_OK'),5)
            p.validate_write_capture(result.stdout,N,stage)
            with self.assertRaises(ValueError):p.validate_write_capture(result.stdout.replace('tx_'+N+' 3 0','tx_'+N+' 4 0'),N,stage)

    def test_freeze_own_probes_before_esd_and_preserve_exact_snapshot(self):
        result,attempts,esd=writer_fixture(mode='esd-after-freeze')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(len(attempts),3);self.assertEqual(esd,'reg_read')
        p.validate_write_capture(result.stdout,N,'candidate14')
        for command in (p.long3_reader(N,'parent_token'),p.write_script(N,'parent_token','sham15')):
            body=shlex.split(command)[8]
            cleanup=body[body.index('cleanup() {'):body.index('trap cleanup EXIT')]
            freeze=cleanup.index('"$T/events/$G/enable"')
            remove=cleanup.index('"-:$G/$e"')
            esd=cleanup.index("reg_read >")
            self.assertLess(cleanup.index('PROFILE_END'),freeze)
            self.assertLess(freeze,remove);self.assertLess(remove,esd)

    def test_external_printf_large_retained_log_and_failed_read(self):
        # Host Linux execve reproduces Android external printf's per-argument cap.
        # First prove old variable-to-argv flow fails with the same retained log.
        result,attempts,esd=writer_fixture(retained_bytes=2*1024*1024,external_printf=True,legacy_kernel_argv=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Argument list too long',result.stderr)
        self.assertEqual(attempts,[]);self.assertEqual(esd,'esd_sw_sim_success')
        for stage in ('sham15','candidate14','return15'):
            result,attempts,esd=writer_fixture(stage,retained_bytes=2*1024*1024,external_printf=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(len(attempts),3);self.assertEqual(esd,'reg_read')
            p.validate_write_capture(result.stdout,N,stage)
        for mode,size in (('dmesg-fail',2*1024*1024),('normal',17*1024*1024)):
            result,attempts,esd=writer_fixture(mode=mode,retained_bytes=size,external_printf=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(attempts,[])
            self.assertEqual(esd,'esd_sw_sim_success')

    def test_gate_storage_and_reader_argv_bounds(self):
        body=shlex.split(p.write_script(N,'parent_token','sham15'))[8]
        gate=body[body.index('previous_count=0'):body.index('cleanup() {')]
        for forbidden in ('kernel=$(', 'snapshot=$(', 'profiles=$(', 'events=$(', 'previous_events='):
            self.assertNotIn(forbidden,gate)
        self.assertIn('cmp -s "$W/gate-prefix" "$W/gate-previous"',gate)
        for name in p.WRITER_GATE_FILES:self.assertIn('"$W/'+name+'"',body)
        for command in (p.long3_reader(N,'parent_token'),p.bounded_c1_reader(N,'parent_token')):
            body=shlex.split(command)[8]
            for variable in ('snapshot','events','profiles'):
                self.assertIn('[ "${#'+variable+'}" -le 16384 ] || return 43',body)

    def test_reader_oversized_profile_rejects_before_external_printf_or_dsi(self):
        parts=shlex.split(p.bounded_c1_reader(N,'parent_token'))
        body=parts[8]
        injection="awk 'BEGIN {for(i=0;i<10000;i++) print \"unrelated_probe_123456789 0 0\"}' >> /sys/kernel/tracing/kprobe_profile\ngate 0\n"
        self.assertEqual(body.count('gate 0\n'),1)
        body=body.replace('gate 0\n',injection).replace("printf '%s\\n' \"$profiles\"", "/usr/bin/printf '%s\\n' \"$profiles\"")
        generated=' '.join(shlex.quote(x) for x in parts[:8])+' '+shlex.quote(body)
        with patch.object(stock,'guarded_reader',return_value=generated):
            result,attempts,esd=execute_reader_fixture()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(attempts,[]);self.assertEqual(esd,'esd_sw_sim_success')
        self.assertNotIn('Argument list too long',result.stderr)

    def test_writer_failures_never_append_dsi_or_esd_enable(self):
        for kind in ('shell-fail','native-fail','bad-wire'):
            for index in (1,2,3):
                with self.subTest(kind=kind,index=index):
                    result,attempts,esd=writer_fixture(mode=f'{kind}-{index}')
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertEqual(len(attempts),index)
                    self.assertEqual(esd,'esd_sw_sim_success')
                    self.assertNotIn('CLEANUP_OK',result.stdout)
        for mode,count in (('extra-wire',1),('pending',1),('flags',1),('misses',2),
                           ('corrupt-prefix',2),('signal-term',2),('signal-hup',2)):
            with self.subTest(mode=mode):
                result,attempts,esd=writer_fixture(mode=mode)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual(len(attempts),count)
                self.assertEqual(esd,'esd_sw_sim_success')

    def test_long3_adapter_real_shell(self):
        original=stock.guarded_reader
        generated=p.long3_reader(N,'parent_token')
        with patch.object(stock,'guarded_reader',return_value=generated):
            result,attempts,esd=execute_reader_fixture()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('0x85',attempts[1]);self.assertNotIn('0xC1',' '.join(attempts))
        value=p.validate_long3(result.stdout,N)
        self.assertEqual(value['opcode'],'85');self.assertEqual(value['response_type'],'DCS_long3')
        for before,after in (('count=9','count=4'),('allocation=16','allocation=4'),
                             ('header=0x1600031c','header=0x00000121'),
                             ('entry_'+N+' 3 0','entry_'+N+' 4 0'),
                             ('P85_LONG3 0x00 0x00 0x60','P85_LONG3 0x15'),
                             ('GATE_OK 4','GATE_OK 5')):
            with self.subTest(before=before),self.assertRaises(ValueError):
                p.validate_long3(result.stdout.replace(before,after),N)
        for mode in ('native-fail-1','native-fail-2','native-fail-3','native-fail-4'):
            with patch.object(stock,'guarded_reader',return_value=generated):
                result,attempts,esd=execute_reader_fixture(mode)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(len(attempts),int(mode[-1]));self.assertEqual(esd,'esd_sw_sim_success')

    def test_shell_scope_and_syntax(self):
        for command in (p.long3_reader(N,'parent_token'),*(p.write_script(N,'parent_token',s) for s in ('sham15','candidate14','return15'))):
            self.assertEqual(subprocess.run(['sh','-n'],input=command,text=True,capture_output=True).returncode,0)
        for stage in ('candidate11','restore','85=00','candidate14; reboot'):
            with self.assertRaises(ValueError):p.write_script(N,'parent_token',stage)
        self.assertFalse(p.LIVE_ENABLED)

    def prepared(self):
        run=p.Rehearsal()
        run.prepare(**dict.fromkeys(('fresh_paths','root_owner','identity','bound_serials','anchor90_120','watchdog','camera_metadata','lead_roi_review'),True))
        return run

    def obs(self,value=0x15,frame=0):
        return p.Observation((value,0,0),(0,0,0x60),(1440,3168,120,120,3,1234000000),3600,'session',frame,frame+60,8,2,True,True)

    def finish(self,run):
        run.finish_write(**dict.fromkeys(('native_returns','wire','prefix','no_misses','pending_flags','state'),True))

    def candidate(self):
        run=self.prepared();run.observe(self.obs())
        run.begin_write('sham15',watchdog_remaining=100);self.finish(run)
        run.observe(self.obs(frame=61));run.begin_write('candidate14',watchdog_remaining=60)
        return run

    def test_full_rehearsal_and_completion_guards(self):
        run=self.candidate();self.finish(run);run.observe(self.obs(0x14,122))
        run.begin_write('return15',watchdog_remaining=30,elapsed_since_candidate=15);self.finish(run)
        run.observe(self.obs(frame=183))
        self.assertTrue(run.candidate_may_be_active)
        kwargs=dict.fromkeys(('stock_optics','camera_stopped','originals_restored','esd_restored','watchdog_disarmed','owner_released'),True)
        with self.assertRaises(ValueError):run.complete(**{**kwargs,'stock_optics':False})
        run.complete(**kwargs);self.assertFalse(run.candidate_may_be_active)
        self.assertEqual(run.stage,'completed');self.assertEqual(run.candidate_attempts,1)

    def test_uncertainty_no_retry_or_cleanup(self):
        for key in ('native_returns','wire','prefix','no_misses','pending_flags','state'):
            run=self.candidate();kwargs=dict.fromkeys(('native_returns','wire','prefix','no_misses','pending_flags','state'),True)
            with self.assertRaises(ValueError):run.finish_write(**{**kwargs,key:False})
            self.assertTrue(run.uncertain)
            for stage in ('return15','candidate14','sham15'):
                with self.assertRaises(ValueError):run.begin_write(stage,watchdog_remaining=60)
            self.assertIn('no further DSI',run.abort())

    def test_bad_observations_and_budget_fail_closed(self):
        base=self.obs(0x14,122)
        for bad in (replace(base,dbv=3601),replace(base,p85=(0x15,0,0)),
                    replace(base,native=(1440,3168,120,1,8,1234000000)),
                    replace(base,camera_session='new'),replace(base,frame_start=2),
                    replace(base,optical_acceptable=False),replace(base,qualified=False)):
            run=self.candidate();self.finish(run)
            with self.assertRaises(ValueError):run.observe(bad)
            self.assertTrue(run.uncertain)
        run=self.candidate();self.finish(run);run.observe(base)
        with self.assertRaises(ValueError):run.begin_write('return15',watchdog_remaining=14,elapsed_since_candidate=46)
        self.assertTrue(run.uncertain)
        with self.assertRaises(ValueError):run.begin_write('return15',watchdog_remaining=60,elapsed_since_candidate=1)


if __name__=='__main__':unittest.main()
