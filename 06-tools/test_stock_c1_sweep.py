"""Offline fixtures/fault injection only; no ADB or phone access."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import stock_c1_sweep as s

N='aabbccddeeff'
BOOT='00000000-0000-0000-0000-000000000001'
ANCHOR='dsi_display_set_mode hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000\n'


def execute_reader_fixture(mode='normal'):
    """Execute the REAL adapted gate/operation/cleanup shell in fake temp files.

    Only hardware-producing printf calls are replaced. Native error returns can
    be injected while printf still succeeds, matching the audited TX bug.
    """
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for name in ('C','T','T/events/pwm_c1_'+N,'W','W/dbg','sys/kernel/tracing','bl'):
            (root/name).mkdir(parents=True,exist_ok=True)
        (root/'T/trace').write_text('')
        (root/'T/tracing_on').write_text('0')
        (root/'bl/brightness').write_text('3600')
        (root/'bl/bl_power').write_text('0')
        (root/'esd').write_text('reg_read\n')
        names=('header','hardware','ctrl','tx','entry')
        (root/'sys/kernel/tracing/kprobe_profile').write_text(''.join(f'{name}_{N} 0 0\n' for name in names))
        body=shlex.split(s.guarded_reader(N,3600,'parent_token'))[8]
        functions=body[body.index("previous_events=''"):body.index('trap cleanup EXIT')]
        tail=body[body.index('touched=1\n'):]
        mock=r'''
umount() { return 0; }
rmdir() { return 0; }
getenforce() { echo Enforcing; }
cat() { if [ "$1" = "$C/rx_cmd" ]; then command printf '0x00 0x00 0x60 '; else command cat "$@"; fi; }
row() { command printf ' printf-%s [004] d... 12345.1: %s_NONCE: %s\n' "$3" "$1" "$2" >> "$T/trace"; }
profiles() {
 : > "$ROOT/sys/kernel/tracing/kprobe_profile"
 for name in header hardware ctrl tx entry; do
  count=$(awk -v name="${name}_NONCE:" 'index($0,name) {n++} END {print n+0}' "$T/trace")
  miss=0; if [ "$MODE" = profile-miss-2 ] && [ "$dsi" = 2 ] && [ "$name" = hardware ]; then miss=1; fi
  command printf '%s_NONCE %s %s\n' "$name" "$count" "$miss" >> "$ROOT/sys/kernel/tracing/kprobe_profile"
 done
}
printf() {
 case "${2-}" in
  '0x39 '*|'3 0x06 '*)
   dsi=$((dsi+1)); command printf '%s\n' "$2" >> "$ROOT/attempts"
   if [ "$MODE" = "shell-fail-$dsi" ]; then return 1; fi
   rc=0; if [ "$MODE" = "native-fail-$dsi" ]; then rc=-5; fi
   if [ "$dsi" = 2 ]; then
    row hardware 'hw_status=0x90000 read_bytes=16 mrps=3' 102
    header=0x1600031c; if [ "$MODE" = bad-header ]; then header=0x0000011c; fi
    row header "header=$header requested=3 count=9 allocation=16 disp_op=0" 102
    if [ "$rc" = 0 ]; then rc=3; fi
    row ctrl "rc=$rc" 102
   else
    pid=$((100+dsi)); row entry 'pending=0 length=11 flags=0' "$pid"
    row ctrl "rc=$rc" "$pid"; row tx "rc=$rc" "$pid"
   fi
   profiles
   if [ "$MODE" = corrupt-prefix ] && [ "$dsi" = 3 ]; then sed -i '1s/12345.1/12345.2/' "$T/trace"; fi
   if [ "$MODE" = signal-hup ] && [ "$dsi" = 2 ]; then kill -HUP $$; fi
   if [ "$MODE" = signal-term ] && [ "$dsi" = 2 ]; then kill -TERM $$; fi
   ;;
 esac
 command printf "$@"
}
'''.replace('NONCE',N)
        setup=(f'set -eu\nROOT={shlex.quote(str(root))}\nMODE={shlex.quote(mode)}\n'
               f'C="$ROOT/C"; E="$ROOT/esd"; T="$ROOT/T"; W="$ROOT/W"; G=pwm_c1_{N}\n'
               'mounted=1; touched=0; traced=1; made_work=0; owned=0; dsi=0\n'
               "P0='0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0'\n"
               "added='"+' '.join(name+'_'+N for name in names)+"'\n")
        script=setup+mock+functions+"trap cleanup EXIT\ntrap 'exit 30' HUP INT TERM\n"+\
               "command printf 'STATE 3600 120.00001\\nESD_INITIAL reg_read\\n'\n"+tail
        script=script.replace('/sys/kernel/tracing/',str(root/'sys/kernel/tracing')+'/')
        # Do not double-substitute the mock's already-prefixed profile path.
        script=script.replace('$ROOT'+str(root/'sys/kernel/tracing'),'$ROOT/sys/kernel/tracing')
        script=script.replace(s.BL,str(root/'bl')+'/')
        result=subprocess.run(['sh'],input=script,text=True,capture_output=True,timeout=5)
        attempts=(root/'attempts').read_text().splitlines() if (root/'attempts').exists() else []
        return result,attempts,(root/'esd').read_text().strip()


class SweepTests(unittest.TestCase):
    def test_successful_real_shell_and_host_validator(self):
        result,attempts,esd=execute_reader_fixture()
        self.assertEqual(result.returncode,0,result.stderr+'\n'+result.stdout)
        self.assertEqual((len(attempts),esd),(4,'reg_read'))
        value=s.validate_adapter_capture(result.stdout,N,3600)
        self.assertEqual(value['data'],[0,0,0x60])
        self.assertTrue(value['in_device_return_gates_verified'])

    def test_shell_native_rx_and_cleanup_failure_stop_next_dsi(self):
        for kind in ('shell-fail','native-fail'):
            for index in range(1,5):
                with self.subTest(kind=kind,index=index):
                    result,attempts,esd=execute_reader_fixture(f'{kind}-{index}')
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertEqual(len(attempts),index,result.stdout)
                    self.assertEqual(esd,'esd_sw_sim_success')
                    self.assertNotIn('CLEANUP_OK',result.stdout)

    def test_signals_bad_header_misses_and_prefix_change(self):
        for mode,count in [('signal-hup',2),('signal-term',2),('bad-header',2),
                           ('profile-miss-2',2),('corrupt-prefix',3)]:
            with self.subTest(mode=mode):
                result,attempts,esd=execute_reader_fixture(mode)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual(len(attempts),count,result.stdout)
                self.assertEqual(esd,'esd_sw_sim_success')

    def test_fixed_scope_and_shell_syntax(self):
        self.assertEqual(s.POINTS,(828,460,2048,3000,3600,828))
        for name in ('bad','../../bad','STOCK_C1_BAD'):
            with self.assertRaises(ValueError):s.plan(name)
        with patch.object(s.c1,'MODULE_SHA','changed'):
            with self.assertRaises(ValueError):s.guarded_reader(N,828,'parent_token')
        body=shlex.split(s.guarded_reader(N,828,'parent_token'))[8]
        self.assertNotIn('0x85',body)
        self.assertNotIn('mkdir -m 700 "$LOCK"',body)
        self.assertNotIn('settings put',body)
        self.assertEqual(subprocess.run(['sh','-n'],input=body,text=True,capture_output=True).returncode,0)
        for command in (s.esd_read_script('/data/local/tmp/stock_c1_test'),
                        s.watchdog_command('/data/local/tmp/stock_c1_test','parent_token',BOOT)):
            self.assertEqual(subprocess.run(['sh','-n'],input=command,text=True,capture_output=True).returncode,0)
        self.assertIn('sleep 600',s.watchdog_command('/tmp/x','parent_token',BOOT))

    def test_native_dispatch_and_same_native_tuple(self):
        log=ANCHOR+'BEGIN\ndsi-ctrl-1: dsi_ctrl_cmd_transfer len=3, type=0x39 hs cmds= 51 01 cc\nEND\n'
        self.assertEqual(s.verify_brightness_dispatch(log,'BEGIN','END',460,828)['native_logged_values'],[460])
        with self.assertRaises(ValueError):s.verify_brightness_dispatch(log,'BEGIN','END',828,460)
        with self.assertRaises(ValueError):s.verify_brightness_dispatch(ANCHOR+'BEGIN\nEND\n','BEGIN','END',460,828)
        with self.assertRaises(ValueError):
            s.verify_brightness_dispatch(ANCHOR+'BEGIN\n'+ANCHOR+'END\n','BEGIN','END',828,828)
        self.assertEqual(s.verify_brightness_dispatch(ANCHOR+'BEGIN\nEND\n','BEGIN','END',828,828)['native_logged_values'],[])
        ref=s.native_state(ANCHOR)
        s.verify_read_interval(ANCHOR+'BEGIN\nEND\n','BEGIN','END',ref)
        with self.assertRaises(ValueError):
            s.verify_read_interval(ANCHOR+'BEGIN\n'+ANCHOR.replace('actual=120, group=0x3','actual=1, group=0x8')+'END\n','BEGIN','END',ref)

    def test_no_restore_commands_while_uncertain(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); run=s.Sweep(None,5,'stock_c1_test',root,root)
            for field in ('pending_read','inflight','recovery_failed'):
                setattr(run,field,True)
                with patch.object(run,'shell') as shell:
                    with self.assertRaises(ValueError):run.restore()
                    shell.assert_not_called()
                setattr(run,field,False)

    def test_reboot_requires_changed_boot_and_only_one_request(self):
        class ADB:
            def __init__(self):self.calls=[]
            def run(self,argv,**kw):self.calls.append(argv);return type('R',(),{'returncode':0})()
            def wait_target(self,serial,timeout):self.calls.append(('wait',serial));return 5
        for changed in (True,False):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                adb=ADB();ticks=[0]
                def clock():ticks[0]+=30;return ticks[0]
                run=s.Sweep(adb,5,'stock_c1_test',directory,directory,sleep=lambda _:None,monotonic=clock)
                run.before={'boot_id':BOOT};run.serial=b'private_serial';run.pending_read=True
                calls=[];boot_reads=[0]
                def shell(command,**kw):
                    calls.append(command)
                    if 'boot_id' in command:
                        boot_reads[0]+=1
                        return BOOT if not changed or boot_reads[0]==1 else BOOT[:-1]+'2'
                    if command=='getprop sys.boot_completed':return '1'
                    if 'panelDC' in command:return '0'
                    if 'esd_check_mode' in command:return 'reg_read'
                    return ''
                with patch.object(run,'shell',side_effect=shell),patch.object(run,'identity') as identity:
                    if changed:
                        run.recover();self.assertFalse(run.pending_read);identity.assert_called_once()
                    else:
                        with self.assertRaises(ValueError):run.recover()
                        self.assertTrue(run.recovery_failed);self.assertTrue(run.pending_read)
                self.assertEqual(len([x for x in adb.calls if isinstance(x,list)]),1)
                self.assertFalse(any('settings put' in x or 'tx_cmd' in x or 'rx_cmd' in x for x in calls))
                self.assertNotIn(BOOT,(Path(directory)/'run.json').read_text())
                self.assertNotIn('private_serial',(Path(directory)/'run.json').read_text())

    def test_restore_failure_preserves_watchdog_and_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            run=s.Sweep(None,5,'stock_c1_test',directory,directory,sleep=lambda _:None)
            run.before={k:'120.0' for k in s.KEYS}
            run.before.update(native_dbv=828,logger=1,screen_brightness_mode='0')
            run.changed=run.armed=run.locked=True
            labels=[]
            def shell(command,**kw):
                labels.append(kw['label'])
                if kw['label']=='restore-power':return '0'
                if kw['label']=='restore-peak':return '90.0'
                if kw['label']=='restore-setting':raise RuntimeError('Injected uncertain restoration')
                return ''
            with patch.object(run,'shell',side_effect=shell):
                with self.assertRaises(RuntimeError):run.restore()
            self.assertNotIn('disarm-watchdog',labels)
            self.assertNotIn('release-owner',labels)
            self.assertNotIn('original_settings_dbv_logger_restored',run.report)

    def test_restore_order_logger_nulls_and_uncertain_disarm(self):
        for fail_disarm in (False,True):
            with self.subTest(fail=fail_disarm),tempfile.TemporaryDirectory() as directory:
                run=s.Sweep(None,5,'stock_c1_test',directory,directory,sleep=lambda _:None)
                run.before=dict(screen_brightness='6',screen_brightness_mode='0',
                                min_refresh_rate='120.0',peak_refresh_rate='null',
                                screen_off_timeout='30000',native_dbv=828,logger=1)
                run.changed=run.armed=run.locked=True
                calls=[]
                def shell(command,**kw):
                    label=kw['label'];calls.append((label,command))
                    if label=='restore-power':return '0'
                    if label=='restore-peak':return '90.0'
                    if label=='poll':return '828'
                    if label=='verify-setting':return run.before[command.split()[-1]]
                    if label=='verify-logger':return 'mipi_cmd_log_en: 1'
                    if label=='final-esd':return 'reg_read'
                    if label=='disarm-watchdog' and fail_disarm:raise RuntimeError('Lost reply')
                    return ''
                with patch.object(run,'shell',side_effect=shell),patch.object(run,'state'):
                    if fail_disarm:
                        with self.assertRaises(RuntimeError):run.restore()
                    else:run.restore()
                commands=[c for _,c in calls];labels=[l for l,_ in calls]
                self.assertLess(commands.index('settings delete system peak_refresh_rate'),
                                commands.index('settings put system min_refresh_rate 120.0'))
                self.assertLess(labels.index('verify-logger'),labels.index('disarm-watchdog'))
                self.assertTrue(run.report['original_settings_dbv_logger_restored'])
                if fail_disarm:
                    self.assertEqual(run.report['watchdog_state'],'disarm_outcome_uncertain')
                    self.assertNotIn('release-owner',labels)
                else:
                    self.assertEqual(run.report['watchdog_state'],'disarmed_verified')
                    self.assertTrue(run.report['mutex_released'])

    def test_offline_check_never_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'new'
            command=['python3','-O',str(Path(s.__file__)),'5','--experiment-id','stock_c1_test_offline',
                     '--output',str(out),'--offline-check']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(out.exists())
            out.mkdir()
            self.assertNotEqual(subprocess.run(command,capture_output=True,text=True).returncode,0)


    def test_execute_read_failure_recovery_and_round_trip_orchestration(self):
        class ADB:
            def preflight(self):pass
            def bind(self,target):return b'private_serial'
        for case in ('success','read_failure_recovered','read_failure_unverified','round_trip_mismatch'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                run=s.Sweep(ADB(),5,'stock_c1_test',directory,directory,sleep=lambda _:None)
                calls=[]
                before={'screen_brightness':'6','screen_brightness_mode':'0',
                        'min_refresh_rate':'120.0','peak_refresh_rate':'120.0','screen_off_timeout':'1800000'}
                def shell(command,**kw):
                    label=kw['label']
                    if label=='prior-kernel':return ANCHOR
                    if label=='before-setting':return before[command.split()[-1]]
                    if label=='before-dbv':return '828'
                    if label=='before-logger':return 'mipi_cmd_log_en: 0'
                    if label=='before-boot':return BOOT
                    if label=='initial-esd':return 'reg_read'
                    if label=='setup-awake':return 'screenState=SCREEN_STATE_ON interactiveState=INTERACTIVE_STATE_AWAKE mIsShowing=false'
                    if label=='extend-timeout':self.assertEqual(command,'settings put system screen_off_timeout 1800000')
                    return ''
                def observe(index,dbv):
                    calls.append(('observe',index))
                    if case.startswith('read_failure') and index==2:
                        run.pending_read=True
                        raise RuntimeError('Uncertain read')
                    value=0x50 if case=='round_trip_mismatch' and index==5 else 0x60
                    run.report['captures'].append({'native_dbv':dbv,'data':[0,0,value]})
                def recover():
                    calls.append(('recover',))
                    if case=='read_failure_unverified':
                        run.recovery_failed=True
                        raise RuntimeError('No changed boot')
                    run.pending_read=run.inflight=False
                    run.report['recovery_reboot_verified']=True
                    run.report['watchdog_state']='inactive_after_verified_reboot'
                def restore():
                    self.assertFalse(run.pending_read or run.inflight or run.recovery_failed)
                    calls.append(('restore',))
                    run.report['original_settings_dbv_logger_restored']=True
                with patch.object(run,'shell',side_effect=shell),patch.object(run,'identity'),\
                     patch.object(run,'state'),patch.object(run,'anchor'),\
                     patch.object(run,'observe',side_effect=observe),\
                     patch.object(run,'recover',side_effect=recover),patch.object(run,'restore',side_effect=restore):
                    if case=='success':run.execute()
                    else:
                        with self.assertRaises(RuntimeError):run.execute()
                if case=='success':
                    self.assertEqual(run.report['status'],'completed')
                    self.assertTrue(run.report['stock828_reference_reproduced'])
                else:
                    self.assertNotEqual(run.report['status'],'completed')
                    self.assertNotIn('stock828_reference_reproduced',run.report)
                if case.startswith('read_failure'):
                    self.assertEqual(calls[:3],[('observe',0),('observe',1),('observe',2)])
                    self.assertEqual(calls[3],('recover',))
                    self.assertEqual(len(run.report['captures']),2)
                    self.assertEqual(('restore',) in calls,case=='read_failure_recovered')
                else:
                    self.assertNotIn(('recover',),calls)
                    self.assertEqual(calls[-1],('restore',))
                public=(Path(directory)/'run.json').read_text()
                self.assertNotIn(BOOT,public);self.assertNotIn('private_serial',public)

    def test_setup_timeout_preserves_longer_original(self):
        self.assertEqual(s.setup_timeout('1800000'),1800000)
        self.assertEqual(s.setup_timeout('30000'),600000)
        self.assertEqual(s.setup_timeout('null'),600000)
        with self.assertRaises(ValueError):s.setup_timeout('invalid')


if __name__=='__main__':unittest.main()
