"""Synthetic exact-boundary tests; no private raw fixture or device actions."""
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


class InitialShellTests(unittest.TestCase):
    def simulate(self, *, before='', after='', cat_fail=False, wc_fail=False):
        real_run=subprocess.run;captured={}
        def execute(args,**kwargs):
            body=args[-1]
            trace=re.search(r'cat (/tmp/[^ ]+/trace) > "\$S"',body)[1]
            Path(trace).write_text(before)
            capture=f'cat {trace} > "$S"'
            if after:
                payload=Path(trace).parent/'after_initial';payload.write_text(after)
                body=body.replace(capture,capture+'\ncat '+shlex.quote(str(payload))+' >> '+shlex.quote(trace),1)
            if cat_fail:
                self.assertEqual(body.count('cat "$S"'),1)
                body=body.replace('cat "$S"','cat "$S"; false')
            if wc_fail:
                body=body.replace('initial_bytes=$(wc -c < "$S")','initial_bytes=$(false)')
            result=real_run([*args[:-1],body],**kwargs)
            captured['trace']=Path(trace).read_text()
            return result
        with patch.object(fixtures.subprocess,'run',side_effect=execute):
            result,ops,mode=fixtures.AATests().simulate_selector()
        return result,ops,mode,captured['trace']

    def test_exact_known_poll_before_snapshot_is_retained_and_qualified(self):
        result,ops,mode,trace=self.simulate(before=REPLAY_POLL)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(len(ops),10)
        initial,body=aa.selector_initial(result.stdout)
        self.assertEqual(initial,REPLAY_POLL);self.assertEqual(body,fixtures.SELECTOR_BODY)
        gap=runtime.validate_safe_gap('',initial,0)
        self.assertEqual(len(gap),1)
        self.assertEqual(aa.validate_selectors(result.stdout,initial,trace,0)['controller_returns'],aa.SELECTOR_CONTROLS)
        self.assertEqual(mode,'esd_sw_sim_success\n')
        with self.assertRaises(ValueError):aa.validate_selectors(result.stdout,'',trace,0)

    def test_poll_after_snapshot_stops_at_first_operation_and_never_held(self):
        for before in ('',REPLAY_POLL):
            result,ops,mode,_=self.simulate(before=before,after=REPLAY_POLL)
            self.assertNotEqual(result.returncode,0);self.assertEqual(ops,['0'])
            initial,_=aa.selector_initial(result.stdout)
            self.assertEqual(initial,before);self.assertNotIn('ESD_HELD',result.stdout)
            self.assertEqual(mode,'esd_sw_sim_success\n')

    def test_unsafe_or_malformed_initial_gap_never_qualifies(self):
        bad=(REPLAY_POLL.replace('rc=1','rc=0'),REPLAY_POLL.replace('kworker/1:2','untrusted'),
             REPLAY_POLL.replace('dsi_display_validate_status','other_caller'),
             REPLAY_POLL.replace('rc=1','rc=garbage'),'unknown trace row\n','mode_ctrl_return\n')
        for event in bad:
            with self.subTest(event=event):
                result,ops,mode,trace=self.simulate(before=event)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(len(ops),10)  # Existing local first-dispatch scope is not expanded.
                with self.assertRaises(ValueError):
                    initial,_=aa.selector_initial(result.stdout)
                    runtime.validate_safe_gap('',initial,0)
                self.assertEqual(mode,'esd_sw_sim_success\n')
        for event in ('LOST\n',REPLAY_POLL.replace('rc=1','rc=-1'),'mode_entry: pending=0 length=11 flags=0\n'):
            result,ops,mode,_=self.simulate(before=event)
            self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
            self.assertEqual(mode,'reg_read\n')

    def test_publication_cat_count_and_oversize_faults_stop_before_isolation(self):
        for kwargs in ({'cat_fail':True},{'wc_fail':True},{'before':'#'+'x'*aa.SELECTOR_INITIAL_LIMIT+'\n'}):
            result,ops,mode,_=self.simulate(**kwargs)
            self.assertNotEqual(result.returncode,0);self.assertEqual(ops,[])
            self.assertEqual(mode,'reg_read\n')
            self.assertNotIn('ESD_ISOLATED',result.stdout)
            with self.assertRaises(ValueError):aa.selector_initial(result.stdout)

    def test_strict_missing_duplicate_truncated_length_and_nul_framing(self):
        raw=fixtures.selector_capture(REPLAY_POLL)
        initial,body=aa.selector_initial(raw)
        self.assertEqual(initial,REPLAY_POLL);self.assertEqual(body,fixtures.SELECTOR_BODY)
        header=raw.split('\n',1)[0]
        bad=(fixtures.SELECTOR_BODY,raw+raw,raw.replace('SELECTOR_INITIAL_END','SELECTOR_INITIAL_END\nSELECTOR_INITIAL_END'),
             raw.replace(header,'SELECTOR_INITIAL_BEGIN 0'),raw.replace(header,'SELECTOR_INITIAL_BEGIN 01'),
             raw.replace(header,'SELECTOR_INITIAL_BEGIN -1'),raw.replace(header,'SELECTOR_INITIAL_BEGIN '+str(aa.SELECTOR_INITIAL_LIMIT+1)),
             raw.replace('SELECTOR_INITIAL_END','END'),raw[:raw.index('SELECTOR_INITIAL_END')],
             'prefix\n'+raw,raw.replace('ESD_HELD','\x00ESD_HELD'),raw+'x'*(4*1024*1024),
             fixtures.selector_capture('# SELECTOR_INITIAL_BEGIN 0\n'))
        for value in bad:
            with self.subTest(value_length=len(value)),self.assertRaises(ValueError):aa.selector_initial(value)

    def test_prefix_change_rejected_and_no_event_is_sliced(self):
        before=REPLAY_POLL
        initial=before.replace('rc=1','rc=0')+REPLAY_POLL
        with self.assertRaises(ValueError):runtime.validate_safe_gap(before,initial,0)
        result,ops,_,trace=self.simulate(before=REPLAY_POLL)
        initial,_=aa.selector_initial(result.stdout)
        with self.assertRaises(ValueError):aa.validate_selectors(result.stdout,initial,trace+REPLAY_POLL,0)

    def test_one_existing_capture_no_extra_wait_and_caps(self):
        body=shlex.split(aa.selector_script(fixtures.TMP,fixtures.TOKEN,0))[-1]
        self.assertEqual(body.count('cat '+aa.TRACE+'/trace > "$S"'),11)
        self.assertEqual(body.count('cat "$S"'),1)
        self.assertLess(body.index('oldc=$(awk'),body.index('SELECTOR_INITIAL_BEGIN'))
        self.assertLess(body.index('SELECTOR_INITIAL_END'),body.index("printf '%s\\n' esd_sw_sim_success"))
        self.assertNotIn('sleep ',body)
        for size in bounded_command_sizes().values():
            self.assertLess(size['service_bytes'],size['service_limit_bytes'])
            self.assertLess(size['shell_argv_bytes_including_nul'],size['argv_limit_bytes'])


class InitialHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):Sim.reader=execute_reader_fixture()[0].stdout
    def execute(self,run):
        with patch.object(runtime.s,'now',run.now):return run.execute()

    def test_before_initial_poll_succeeds_with_exact_provenance_in_all_five_selectors(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.selector_initial_suffix=REPLAY_POLL
            report=self.execute(run)
        runtime.acquisition.validate_acquisition(report)
        runtime.qualification(report,{k:report[k] for k in ('source_commit','source_blob_ids')})
        seen=0
        for i,stage in enumerate(report['stages']):
            for side in (('selectors_before_hold',) if i==1 else ('selectors_before_hold','selectors_after_hold')):
                boundary=stage[side]['trace_boundary'];seen+=1
                self.assertEqual(boundary['initial_event_count'],boundary['outer_event_count']+1)
                self.assertEqual(len(boundary['safe_gap_events']),1)
                self.assertNotEqual(boundary['outer_before_sha256'],boundary['initial_sha256'])
                runtime.acquisition.validate_selector_boundary(stage[side])
        self.assertEqual(seen,5)

    def test_unknown_before_or_any_after_initial_event_reboots_without_restore(self):
        for field,event in (('selector_initial_suffix',REPLAY_POLL.replace('rc=1','rc=0')),
                            ('selector_initial_suffix','malformed trace\n'),('selector_after_initial_suffix',REPLAY_POLL)):
            with self.subTest(field=field,event=event),tempfile.TemporaryDirectory() as root:
                run=Sim(root);setattr(run,field,event)
                with self.assertRaises(RuntimeError):self.execute(run)
                self.assertEqual(run.calls.count('reboot'),1)
                self.assertNotIn('baseline-before-hold-selector-esd',run.calls)
                self.assertNotIn('baseline-c1',run.children)

    def test_missing_initial_legacy_child_is_terminal_and_pending_stays_latched(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.setup();run.setup_aa();run.selector_raw=fixtures.SELECTOR_BODY
            with self.assertRaisesRegex(ValueError,'snapshot'):run.selectors('test')
            self.assertTrue(run.pending_read);self.assertEqual(run.esd_mode,'esd_sw_sim_success')
            calls=list(run.calls)
            for operation in (lambda:run.selectors('later'),lambda:run.c1('later'),lambda:run.replay('later'),lambda:run.writer('baseline')):
                with self.assertRaises(ValueError):operation()
            self.assertEqual(run.calls,calls)

    def test_consumers_reject_missing_changed_or_fabricated_boundary_contract(self):
        with tempfile.TemporaryDirectory() as root:
            run=Sim(root);run.selector_initial_suffix=REPLAY_POLL;report=self.execute(run)
        source={k:report[k] for k in ('source_commit','source_blob_ids')}
        mutations=(lambda b:b.clear(),lambda b:b.update(contract='old'),lambda b:b.update(initial_source='synthesized'),
                   lambda b:b.update(capture='after_dispatch'),lambda b:b.update(outer_before_sha256='x'*64),
                   lambda b:b.update(initial_sha256=''),lambda b:b.update(outer_event_count=True),
                   lambda b:b.update(initial_event_count=b['initial_event_count']+1),lambda b:b.update(entry_count_before=999),
                   lambda b:b.update(safe_gap_events=[]),lambda b:b['safe_gap_events'][0].update(return_code=0),
                   lambda b:b['safe_gap_events'][0].update(caller='other'),lambda b:b['safe_gap_events'][0].update(timestamp=float('nan')),
                   lambda b:b['safe_gap_events'][0].update(extra='unqualified'),lambda b:b.update(extra=True))
        for index in range(3):
            for side in (('selectors_before_hold',) if index==1 else ('selectors_before_hold','selectors_after_hold')):
                for mutation in mutations:
                    changed=deepcopy(report);mutation(changed['stages'][index][side]['trace_boundary'])
                    with self.assertRaises(ValueError):runtime.acquisition.validate_acquisition(changed)
                    with self.assertRaises(ValueError):runtime.qualification(changed,source)


if __name__=='__main__':unittest.main()
