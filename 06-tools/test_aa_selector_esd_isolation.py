"""Synthetic selector boundary regressions. No transport/device evidence input."""
from copy import deepcopy
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import aa_threshold_trial as aa
import run_aa_timed_stock_trial as runtime
import test_aa_threshold_trial as fixtures
from test_run_aa_timed_stock_trial import Sim, REPLAY_POLL
from test_stock_c1_sweep import execute_reader_fixture
from test_aa_writer_esd_isolation import bounded_command_sizes


class SelectorShellTests(unittest.TestCase):
    def test_final_readback_failure_never_reports_held_or_restores(self):
        real_run = subprocess.run
        for wrong in (False, True):
            def run(args, **kwargs):
                body=args[-1]
                # Initial mode reads stay unchanged; fail only final mode5 readback.
                needle=aa.esd_mode_guard('esd_sw_sim_success')
                self.assertEqual(body.count(needle),1)
                prefix = "printf '%s\\n' wrong > \"$E\"\n" if wrong else 'tr() { command tr "$@"; return 93; };\n'
                body=body.replace(needle,prefix+needle)
                return real_run([*args[:-1],body],**kwargs)
            with patch.object(fixtures.subprocess,'run',side_effect=run):
                result,ops,mode=fixtures.AATests().simulate_selector()
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(len(ops),10)
            self.assertNotIn('ESD_HELD',result.stdout)
            self.assertNotIn('ESD_RESTORED',result.stdout)
            self.assertEqual(mode,'wrong\n' if wrong else 'esd_sw_sim_success\n')

    def test_success_never_restores_in_child_or_error_trap(self):
        result,ops,mode=fixtures.AATests().simulate_selector()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(ops),10)
        self.assertEqual(mode,'esd_sw_sim_success\n')
        self.assertEqual(result.stdout,fixtures.SELECTOR_RAW)
        body=shlex.split(aa.selector_script(fixtures.TMP,fixtures.TOKEN,0))[-1]
        self.assertNotIn("printf '%s\\n' reg_read",body)
        self.assertNotIn('sleep ',body)
        self.assertLess(body.rindex('oldc=$(awk'),body.index(aa.esd_mode_guard('esd_sw_sim_success')))
        self.assertTrue(all('reg_read' not in line and 'tx_cmd' not in line for line in body.splitlines() if line.startswith('trap ')))

    def test_old_restored_child_and_unowned_outer_events_rejected(self):
        trace=''
        for i,rc in enumerate(aa.SELECTOR_CONTROLS):
            page=i not in (1,4,7)
            trace+=('mode_entry: pending=0 length=11 flags=0\n' if page else '')+f'mode_ctrl_return: rc={rc}\n'+('mode_return: rc=0\n' if page else '')
        aa.validate_selectors(fixtures.SELECTOR_RAW,'',trace,0)
        with self.assertRaises(ValueError):
            aa.validate_selectors(fixtures.SELECTOR_RAW.replace('ESD_HELD esd_sw_sim_success','ESD_RESTORED reg_read'),'',trace,0)
        for bad in (REPLAY_POLL+trace,trace+REPLAY_POLL,trace.replace('rc=2','rc=1'),trace.replace('pending=0','pending=1',1),trace+'LOST\n'):
            with self.assertRaises(ValueError):aa.validate_selectors(fixtures.SELECTOR_RAW,'',bad,0)

    def test_command_caps_unchanged(self):
        for sizes in bounded_command_sizes().values():
            self.assertLess(sizes['service_bytes'],sizes['service_limit_bytes'])
            self.assertLess(sizes['shell_argv_bytes_including_nul'],sizes['argv_limit_bytes'])


class SelectorHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout

    def execute(self,run):
        with patch.object(runtime.s,'now',run.now):return run.execute()

    def ready(self,root):
        run=Sim(root);run.setup();run.setup_aa();return run

    def test_hold_through_validation_cursor_before_restore_and_caller_latch(self):
        with tempfile.TemporaryDirectory() as root:
            run=self.ready(root);run.panel_uncertain=True
            original=run.shell;validate=aa.validate_selectors;native=runtime.s.verify_read_interval
            checks=[]
            def validation(*args,**kwargs):
                self.assertEqual(run.esd_mode,'esd_sw_sim_success');checks.append('trace')
                return validate(*args,**kwargs)
            def interval(*args,**kwargs):
                self.assertEqual(run.esd_mode,'esd_sw_sim_success');checks.append('native')
                return native(*args,**kwargs)
            def shell(command,**kwargs):
                if kwargs.get('label')=='test-selector-esd':
                    self.assertEqual(checks,['trace','native'])
                    self.assertTrue(run.pending_read);self.assertTrue(run.panel_uncertain)
                    self.assertIs(kwargs.get('mutation'),True)
                    self.assertEqual(run.entry_count,7);self.assertEqual(run.trace_snapshot,run.trace)
                    value=original(command,**kwargs)
                    run.trace+=REPLAY_POLL
                    return value
                return original(command,**kwargs)
            run.shell=shell
            with patch.object(aa,'validate_selectors',side_effect=validation),patch.object(runtime.s,'verify_read_interval',side_effect=interval):
                record=run.selectors('test')
            self.assertFalse(run.pending_read);self.assertTrue(run.panel_uncertain)
            self.assertEqual(record['entry_count_after'],7)
            self.assertEqual(run.trace,run.trace_snapshot+REPLAY_POLL)
            runtime.acquisition.validate_selector_lifecycle(record)
            run.trace_check(run.trace)
            self.assertEqual(len(run.report['background_esd_safe_gaps']),1)

    def test_every_envelope_or_host_fault_prevents_restore_and_reboots(self):
        faults={
            'raw':('CHILD',lambda x:x.replace('ESD_HELD','ESD_RESTORED')),
            'extra_control':('TRACE_AFTER',lambda x:x+REPLAY_POLL),
            'wrong_entry':('TRACE_AFTER',lambda x:x.replace('length=11','length=12')),
            'prefix':('TRACE_AFTER',lambda x:'CORRUPT\n'+x.replace('mode_ctrl_return: rc=0','mode_ctrl_return: rc=1',1)),
            'trace_guard':('TRACE_GUARD',lambda x:'BAD\n'),
            'trace_owner':('TRACE_OWNER',lambda x:'unexpected'),
            'state':('FIELDS',lambda x:'3599\n0\n0\nEnforcing\n'),
            'boot':('BOOT',lambda x:'00000000-0000-0000-0000-000000000000\n'),
            'native':('KERNEL',lambda x:x.replace('BASELINE_BEFORE_HOLD_BEGIN\n','BASELINE_BEFORE_HOLD_BEGIN\ndsi_display_set_mode failure\n')),
        }
        for name,(part,mutate) in faults.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.part_faults={('baseline-before-hold',part):mutate}
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertNotIn('baseline-before-hold-selector-esd',run.calls)
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('baseline-c1',run.children)

    def test_restore_faults_real_shell_latch_no_success_or_later_dsi(self):
        # Use the real inherited shell/DeadlineTransport for the restoration,
        # not Sim.shell's shortcut, while keeping the device endpoint synthetic.
        for fault in ('timeout','nonzero','wrongmarker','late','success'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                run=self.ready(root);original=run.shell;run.active_start=run.clock()
                class RestoreTransport:
                    def shell(_self,target,command,timeout):
                        self.assertTrue(run.inflight);self.assertTrue(run.pending_read)
                        self.assertEqual(run.entry_count,7)
                        self.assertEqual(run.trace_snapshot,run.trace)
                        if fault=='timeout':raise TimeoutError('synthetic restoration timeout')
                        if fault=='late':run.clock.sleep(38)
                        if fault=='nonzero':return 1,b'',b'failure'
                        return 0,(b'wrong' if fault=='wrongmarker' else b'WRITER_ESD_RESTORED reg_read\n'),b''
                def shell(command,**kwargs):
                    if kwargs.get('label')!='test-selector-esd':return original(command,**kwargs)
                    old=run.g;run.g=runtime.timed.DeadlineTransport(run,RestoreTransport())
                    try:return runtime.AATimedTrial.shell(run,command,**kwargs)
                    finally:run.g=old
                run.shell=shell
                if fault=='success':
                    run.selectors('test');self.assertFalse(run.pending_read);self.assertFalse(run.inflight)
                else:
                    with self.assertRaises((ValueError,TimeoutError)):run.selectors('test')
                    self.assertTrue(run.pending_read)
                    self.assertEqual(run.inflight,fault!='wrongmarker')
                    calls=list(run.calls)
                    for operation in (lambda:run.selectors('later'),lambda:run.c1('later'),lambda:run.replay('later'),lambda:run.writer('baseline'),lambda:run.prehold({'label':'baseline'}),lambda:run.finish_hold({'label':'baseline'})):
                        with self.assertRaises(ValueError):operation()
                    self.assertEqual(run.calls,calls)

    def test_full_run_restore_errors_reboot_without_successful_stage(self):
        for label in ('baseline-before-hold','baseline-after-hold','sham_stock-before-hold','return_stock-before-hold','return_stock-after-hold'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as root:
                run=Sim(root);run.failure=label+'-selector-esd'
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('return_hold_and_postselectors_verified',run.report)

    def test_consumer_and_stock_qualification_reject_legacy_or_invalid_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:report=self.execute(Sim(root))
        source={k:report[k] for k in ('source_commit','source_blob_ids')}
        runtime.acquisition.validate_acquisition(report);runtime.qualification(report,source)
        mutations=(lambda e:e.clear(),lambda e:e.update(final_child_readback=False),lambda e:e.update(final_child_readback=1),lambda e:e.update(inflight_cancellation_proven=True),lambda e:e.update(contract='legacy'),lambda e:e.update(held_through='child_only'),lambda e:e.update(restored_monotonic=e['validated_monotonic']-1),lambda e:e.update(validated_monotonic=float('nan')),lambda e:e.update(extra=True))
        for index in range(3):
            for side in (('selectors_before_hold',) if index==1 else ('selectors_before_hold','selectors_after_hold')):
                for mutate in mutations:
                    broken=deepcopy(report);mutate(broken['stages'][index][side]['esd_lifecycle'])
                    with self.assertRaises(ValueError):runtime.acquisition.validate_acquisition(broken)
                    with self.assertRaises(ValueError):runtime.qualification(broken,source)
                broken=deepcopy(report);broken['stages'][index][side]['esd_lifecycle'].update(validated_monotonic=0,restored_monotonic=0)
                with self.assertRaises(ValueError):runtime.acquisition.validate_acquisition(broken)


if __name__=='__main__':unittest.main()
