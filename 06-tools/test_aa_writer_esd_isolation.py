"""Offline real generated-shell and lifecycle faults. Never calls a device."""
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import aa_threshold_trial as aa
import run_aa_timed_stock_trial as runtime
import test_aa_threshold_trial as shell_fixtures
from test_aa_threshold_trial import TMP, TOKEN
from test_run_aa_timed_stock_trial import Sim, REPLAY_POLL
from test_stock_c1_sweep import execute_reader_fixture


def bounded_command_sizes():
    """Conservative construction fixture, not a physical transport bound."""
    tmp = '/data/local/tmp/' + 'w'*100
    token = 't'*128
    nonce = 'a'*12
    owner = aa.lock_commands(token)['verify']
    owner += (f'; test ! -L {tmp}/main-trace-owner; test "$(cat {tmp}/main-trace-owner)" = {token}; '
              f'test "$(cat {aa.TRACE}/tracing_on)" = 1')
    # Six-digit event/count fields exceed this three-stage caller's callback
    # count and cover a full 4 MiB snapshot of the shortest recognized events.
    before = 'mode_ctrl_return: rc=1\n'*199999
    result = {}
    for name in ('stock', 'aa10', 'selectors', 'c1'):
        if name in ('stock', 'aa10'):
            child = aa.writer_script(tmp, token, aa.fixed_programs()[name], name, 999999)
        elif name == 'selectors':
            child = aa.selector_script(tmp, token, 999999)
        else:
            child = runtime.timed.p85.bounded_c1_reader(nonce, token)
        guard = ('00000000-0000-0000-0000-000000000000', 'Q'*180, nonce) if name in ('stock', 'aa10') else None
        plan = runtime.child_plan(nonce, owner, child, 'B'*180, 'E'*180, guard=guard)
        parts = list(plan.parts)
        index = next(i for i, part in enumerate(parts) if part.label == 'CHILD')
        parts.insert(index, runtime.env.Part('TRACE_GUARD', runtime.trace_guard(tmp, owner, before), True, 64, 8))
        plan = replace(plan, parts=(runtime.env.Part('TRACE_OWNER', owner, True, 0),)+tuple(parts))
        result[name] = runtime.env.command_sizes(runtime.env.script(plan))
    for restore in (False, True):
        name = 'esd_restore' if restore else 'esd_isolate'
        result[name] = runtime.env.command_sizes('su -c '+shlex.quote(aa.writer_esd_script(tmp, token, restore=restore)))
    return result


class GeneratedShellTests(unittest.TestCase):
    def transition(self, *, restore=False, initial=None, fault=None):
        """Replace only ownership/mount/native file I/O; run real shell guards."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            (root/'debugfs').mkdir(mode=0o700)
            esd = root/'debugfs'/aa.ESD_MODE_PATH
            esd.parent.mkdir(parents=True)
            before = 'esd_sw_sim_success' if restore else 'reg_read'
            after = 'reg_read' if restore else 'esd_sw_sim_success'
            esd.write_bytes(initial if initial is not None else before.encode()+b'\0\n')
            body = shlex.split(aa.writer_esd_script(TMP, TOKEN, restore=restore))[-1]
            body = body.replace(aa.lock_commands(TOKEN)['verify'], ':').replace(TMP, str(root))
            body = re.sub(r'(stat -c %u [^\n]+\)" = )0', lambda m: m[1]+str(os.getuid()), body)
            prefix = 'mount() { :; }; umount() { :; };\n'
            if fault == 'unmount':
                prefix = 'mount() { :; }; umount() { return 92; };\n'
            write = "printf '%s\\n' "+after+' > "$E"'
            self.assertEqual(body.count(write), 1)
            if fault == 'ignored_write':
                body = body.replace(write, ': # Native setter returned success without changing mode')
            elif fault == 'write_error':
                body = body.replace(write, 'false')
            elif fault == 'wrong_readback':
                body = body.replace(write, "printf '%s\\n' unexpected > \"$E\"")
            elif fault in ('initial_read', 'final_read'):
                target = 1 if fault == 'initial_read' else 2
                # A failed read may emit exactly the expected text. Its nonzero
                # status must still abort before the next transition/marker.
                prefix += ('tr() { n=$(cat "$COUNT"); n=$((n+1)); printf %s "$n" > "$COUNT"; '
                           'command tr "$@"; if [ "$n" = '+str(target)+' ]; then return 93; fi; };\n')
                (root/'count').write_text('0')
            result = subprocess.run(['sh', '-c', prefix+body], capture_output=True, text=True,
                                    env={**os.environ, 'COUNT': str(root/'count')}, timeout=10)
            return result, esd.read_bytes()

    def test_exact_lf_transitions_and_existing_readback_contract(self):
        for restore in (False, True):
            result, contents = self.transition(restore=restore)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = 'reg_read' if restore else 'esd_sw_sim_success'
            self.assertEqual(contents, after.encode()+b'\n')
            self.assertEqual(result.stdout, ('WRITER_ESD_RESTORED ' if restore else 'WRITER_ESD_ISOLATED ')+after+'\n')
            body = shlex.split(aa.writer_esd_script(TMP, TOKEN, restore=restore))[-1]
            self.assertNotIn('tx_cmd', body)
            self.assertNotIn('rx_cmd', body)
            self.assertNotIn('sleep ', body)
            self.assertNotIn('reg_read', next(line for line in body.splitlines() if line.startswith('trap ')))

    def test_transition_faults_are_not_success_and_never_trap_restore(self):
        for restore in (False, True):
            before = 'esd_sw_sim_success' if restore else 'reg_read'
            after = 'reg_read' if restore else 'esd_sw_sim_success'
            for fault in ('ignored_write', 'write_error', 'wrong_readback', 'initial_read', 'final_read', 'unmount'):
                with self.subTest(restore=restore, fault=fault):
                    result, contents = self.transition(restore=restore, fault=fault)
                    self.assertNotEqual(result.returncode, 0)
                    if fault in ('ignored_write', 'write_error', 'initial_read'):
                        self.assertEqual(contents, before.encode()+b'\0\n')
                    elif fault in ('final_read', 'unmount'):
                        self.assertEqual(contents, after.encode()+b'\n')
                    if fault != 'unmount':
                        self.assertEqual(result.stdout, '')
            for initial in (b'', b'bad\n', before.encode()+b' extra\n'):
                result, contents = self.transition(restore=restore, initial=initial)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(contents, initial)

    def test_writer_requires_isolation_before_any_dd(self):
        fixtures = shell_fixtures.AATests()
        for name in ('stock', 'aa10'):
            for mode in ('reg_read\n', '', 'esd_sw_sim_success extra\n'):
                result, executed, retained = fixtures.simulate_writer(name, esd_mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(executed, [])
                self.assertTrue(retained)
            result, executed, _ = fixtures.simulate_writer(name)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(executed, ['0', '1', '2', '3', '4'])
            self.assertTrue(result.stdout.startswith('WRITER_ESD_ISOLATED esd_sw_sim_success\n'))
            body = shlex.split(aa.writer_script(TMP, TOKEN, aa.fixed_programs()[name], name, 0))[-1]
            self.assertNotIn("printf '%s\\n' reg_read", body)
            self.assertLess(body.index('test "$esd_mode"'), body.index('dd if='))

    def test_incomplete_old_callback_and_every_new_controller_event_fail_closed(self):
        fixtures = shell_fixtures.AATests()
        result, executed, _ = fixtures.simulate_writer('stock', initial_trace='mode_entry: pending=0 length=11 flags=0\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(executed, [])
        for index in range(5):
            result, executed, retained = fixtures.simulate_writer('stock', controller_at=index)
            self.assertEqual(result.returncode, 51)
            self.assertEqual(executed, list(map(str, range(index+1))))
            self.assertTrue(retained)
            with self.assertRaises(ValueError):
                aa.tx.validate_batch_capture(result.stdout, 0)

    def test_encoded_commands_stay_below_service_and_argv_caps(self):
        for sizes in bounded_command_sizes().values():
            self.assertLess(sizes['service_bytes'], sizes['service_limit_bytes'])
            self.assertLess(sizes['shell_argv_bytes_including_nul'], sizes['argv_limit_bytes'])

    def test_transition_arguments_are_fixed(self):
        for restore in (0, 1, None, 'restore'):
            with self.assertRaises(ValueError):
                aa.writer_esd_script(TMP, TOKEN, restore=restore)
        with self.assertRaises(ValueError):
            aa.esd_mode_guard('other')


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Sim.reader = execute_reader_fixture()[0].stdout

    def execute(self, run):
        with patch.object(runtime.s, 'now', run.now):
            return run.execute()

    def test_success_keeps_sim_through_all_evidence_and_both_wire_validations(self):
        with tempfile.TemporaryDirectory() as root:
            run = Sim(root)
            original = aa.validate_wire
            validations = []
            def wire(*args, **kwargs):
                self.assertEqual(run.esd_mode, 'esd_sw_sim_success')
                validations.append(run.children[-1])
                return original(*args, **kwargs)
            with patch.object(aa, 'validate_wire', side_effect=wire):
                report = self.execute(run)
            runtime.acquisition.validate_acquisition(report)
            self.assertEqual(len(validations), 6)
            self.assertEqual(run.esd_mode, 'reg_read')
            for stage in ('baseline', 'sham_stock', 'return_stock'):
                positions = [run.calls.index(stage+'-writer-isolate'), run.calls.index('quiet-'+stage+'_PRE'),
                             run.calls.index(stage+'-write'), run.calls.index(stage+'-writer-esd'),
                             run.calls.index(stage+'-replay')]
                self.assertEqual(positions, sorted(positions))
            self.assertEqual(report['candidate_attempts'], 0)
            self.assertLess(report['active_G_seconds'], 37)

    def test_isolation_quiet_and_restore_failures_reboot_without_next_child(self):
        for label in ('baseline-writer-isolate', 'quiet-baseline_PRE', 'baseline-writer-esd',
                      'sham_stock-writer-isolate', 'return_stock-writer-esd'):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as root:
                run = Sim(root)
                run.failure = label
                with self.assertRaises(RuntimeError):
                    self.execute(run)
                self.assertEqual(run.calls.count('reboot'), 1)
                self.assertNotIn('return_hold_and_postselectors_verified', run.report)
                if label in ('baseline-writer-isolate', 'quiet-baseline_PRE'):
                    self.assertEqual(run.children, [])
                    self.assertEqual(run.report['full_table_writes_attempted'], [])
                elif label == 'baseline-writer-esd':
                    self.assertEqual(run.children, ['baseline-write'])
                    self.assertNotIn('baseline-replay', run.calls)
                self.assertEqual(run.esd_mode, 'reg_read')  # Recovery, not trap restoration.

    def test_native_activity_during_quiet_stops_before_first_dd(self):
        with tempfile.TemporaryDirectory() as root:
            run = Sim(root)
            run.part_faults = {('quiet-baseline_PRE', 'KERNEL'):
                              lambda value: value+'dsi_ctrl_cmd_transfer len=1\n'}
            with self.assertRaises(RuntimeError):
                self.execute(run)
            self.assertEqual(run.children, [])
            self.assertEqual(run.calls.count('reboot'), 1)
            self.assertNotIn('baseline-writer-esd', run.calls)

    def test_missing_or_wrong_transition_readback_is_sticky_and_recovers(self):
        for label in ('baseline-writer-isolate', 'baseline-writer-esd'):
            for response in ('', 'reg_read', 'WRITER_ESD_RESTORED esd_sw_sim_success'):
                with self.subTest(label=label, response=response), tempfile.TemporaryDirectory() as root:
                    run = Sim(root)
                    original = run.shell
                    def shell(command, **kwargs):
                        value = original(command, **kwargs)
                        return response if kwargs.get('label') == label else value
                    run.shell = shell
                    with self.assertRaises(RuntimeError):
                        self.execute(run)
                    self.assertEqual(run.calls.count('reboot'), 1)
                    self.assertNotIn('baseline-replay', run.calls)
                    self.assertNotIn('baseline-before-hold', run.calls)
                    self.assertNotIn('baseline-hold-start', run.calls)
                    self.assertEqual(run.children, ['baseline-write'] if label.endswith('-esd') else [])

    def test_failed_host_validation_never_restores_esd(self):
        faults = {
            'child_mode': ('CHILD', lambda value: value.replace('WRITER_ESD_ISOLATED', 'BAD_MODE', 1)),
            'initial_trace': ('CHILD', lambda value: value.replace('BLOCK_TRACE_BEGIN -1\n', 'BLOCK_TRACE_BEGIN -1\n'+REPLAY_POLL, 1)),
            'deferred_esd': ('CHILD', lambda value: value.replace('BLOCK_TRACE_END 2', REPLAY_POLL+'BLOCK_TRACE_END 2', 1)),
            'late_native': ('TRACE_AFTER', lambda value: value+REPLAY_POLL),
            'wire': ('KERNEL', lambda value: value.replace('aa 11', 'aa 10', 1)),
            'after_end_wire': ('KERNEL', lambda value: value+'dsi_ctrl_cmd_transfer len=1\n'),
            'state': ('FIELDS', lambda value: '3599\n0\n0\nEnforcing\n'),
            'boot': ('BOOT', lambda value: '00000000-0000-0000-0000-000000000000\n'),
        }
        for name, (part, mutate) in faults.items():
            with self.subTest(fault=name), tempfile.TemporaryDirectory() as root:
                run = Sim(root)
                run.part_faults = {('baseline-write', part): mutate}
                with self.assertRaises(RuntimeError):
                    self.execute(run)
                self.assertEqual(run.children, ['baseline-write'])
                self.assertNotIn('baseline-writer-esd', run.calls)
                self.assertEqual(run.calls.count('reboot'), 1)

    def test_caught_error_blocks_every_later_dsi_entrypoint(self):
        for failure in ('baseline-writer-isolate', 'quiet-baseline_PRE', 'baseline-writer-esd'):
            with tempfile.TemporaryDirectory() as root:
                run = Sim(root)
                run.setup(); run.setup_aa()
                run.failure = failure
                with self.assertRaises((ValueError, TimeoutError)):
                    run.writer('baseline')
                calls = list(run.calls)
                for operation in (lambda: run.writer('baseline'), lambda: run.selectors('later'),
                                  lambda: run.c1('later'), lambda: run.replay('later'),
                                  lambda: run.prehold({'label': 'later'}),
                                  lambda: run.finish_hold({'label': 'later'})):
                    with self.assertRaises(ValueError):
                        operation()
                self.assertEqual(run.calls, calls)
                self.assertTrue(run.pending_read)
                self.assertTrue(run.panel_uncertain)

    def test_known_completed_old_esd_only_accepted_before_writer_or_after_restore(self):
        for before in (True, False):
            with tempfile.TemporaryDirectory() as root:
                run = Sim(root)
                original = run.shell
                def shell(command, **kwargs):
                    value = original(command, **kwargs)
                    label = kwargs.get('label')
                    target = 'baseline-writer-isolate' if before else 'baseline-writer-esd'
                    if label == target:
                        run.trace += REPLAY_POLL
                    return value
                run.shell = shell
                report = self.execute(run)
                self.assertEqual(len(report['background_esd_safe_gaps']), 1)
                self.assertNotIn('reboot', run.calls)
                runtime.acquisition.validate_acquisition(report)

    def test_acquisition_rejects_lifecycle_omission_mismatch_and_wrong_order(self):
        with tempfile.TemporaryDirectory() as root:
            report = self.execute(Sim(root))
        changes = [lambda x: x.clear(), lambda x: x.update(inflight_cancellation_proven=True),
                   lambda x: x.update(pre_first_chunk_readback=False),
                   lambda x: x.update(held_through='child_only'),
                   lambda x: x.update(isolated_monotonic=x['quiet_verified_monotonic']),
                   lambda x: x.update(restored_monotonic=x['table_validated_monotonic']-1),
                   lambda x: x.update(extra='unqualified')]
        for change in changes:
            for stage_only in (False, True):
                broken = deepcopy(report)
                change(broken['stages'][0]['esd_lifecycle'])
                if not stage_only:
                    broken['writes'][0]['esd_lifecycle'] = deepcopy(broken['stages'][0]['esd_lifecycle'])
                with self.assertRaises(ValueError):
                    runtime.acquisition.validate_acquisition(broken)


if __name__ == '__main__':
    unittest.main()
