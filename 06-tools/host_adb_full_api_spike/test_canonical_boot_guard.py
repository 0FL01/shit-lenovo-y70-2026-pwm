"""Inactive proposed patch tests: AST methods, fake I/O, no runtime imports.

Reads only pinned source/proposal artifacts. No subprocess/socket/device/file
creation from tested code. Shell fixtures represent already stripped stdout,
matching Sweep.shell's existing public return contract, not raw wire bytes.
"""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import shlex
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'stock_c1_sweep.py'
PIN = '68e529befbc91e7b3273149ced23670fb9789f1bb586ae859484bed8637bf5fd'
OLD = "                    if boot!=self.before['boot_id'] and complete=='1':break\n"
NEW = """                    if (re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', self.before['boot_id'])
                        and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot)
                        and boot!=self.before['boot_id'] and complete=='1'):break
"""
BEFORE = '11111111-1111-4111-8111-111111111111'
AFTER = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
IDENTITY = '\n'.join(['XT2611-1','W3WWS36.65-64-4-1','_b',
    '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k','Enforcing','avr'])


def check(condition, message):
    if not condition:
        raise ValueError(message)


def source_pair():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise RuntimeError('Pinned source changed; review again')
    source = raw.decode()
    if source.count(OLD) != 1:
        raise RuntimeError('Exact acceptance predicate changed')
    proposed = source.replace(OLD, NEW)
    diff = ''.join(difflib.unified_diff(source.splitlines(True), proposed.splitlines(True),
        fromfile='a/06-tools/stock_c1_sweep.py', tofile='b/06-tools/stock_c1_sweep.py'))
    if diff != (HERE / 'canonical_boot_guard.proposed.patch').read_text():
        raise RuntimeError('Proposed patch differs from tested source')
    binding = json.loads((HERE / 'boot_guard_source_binding.json').read_text())
    if (binding['original_sha256'] != PIN or binding['applied_to_runtime'] is not False
            or binding['proposed_in_memory_sha256'] != hashlib.sha256(proposed.encode()).hexdigest()
            or binding['patch_sha256'] != hashlib.sha256(diff.encode()).hexdigest()):
        raise RuntimeError('Proposal identity binding changed')
    return source, proposed


def extracted_class(proposed):
    tree = ast.parse(proposed)
    sweep = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Sweep')
    methods = [n for n in sweep.body if isinstance(n, ast.FunctionDef)
               and n.name in ('recover', 'identity', 'restore')]
    if {n.name for n in methods} != {'recover', 'identity', 'restore'}:
        raise RuntimeError('Missing real methods')
    # Compile actual source method bodies, not a rewritten state machine.
    module = ast.Module(body=methods + [next(n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == 'esd_read_script')], type_ignores=[])
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('CON','MODULE_SHA')}
    namespace = dict(constants, check=check, re=re, q=shlex.quote,
                     c1=SimpleNamespace(PANEL='fixture-panel'))
    exec(compile(ast.fix_missing_locations(module), '<pinned-proposed-methods>', 'exec'), namespace)
    return type('ProposedSweep', (), {name: namespace[name] for name in ('recover','identity','restore')}), namespace


class FakeADB:
    def __init__(self, reboot_error=False):
        self.calls = []
        self.reboot_error = reboot_error
    def run(self, argv, **kwargs):
        self.calls.append(('run', argv, kwargs))
        if self.reboot_error:
            raise TimeoutError('fixture uncertain reboot')
        return SimpleNamespace(returncode=0)
    def wait_target(self, serial, timeout):
        self.calls.append(('wait', serial, timeout))
        return 9  # Original alias 7 remains bound by the transport contract.


def fixture(cls, namespace, observed, *, saved=BEFORE, complete='1', reboot_error=False,
            fail_label=None):
    run = cls()
    run.g = FakeADB(reboot_error)
    run.target, run.serial = 7, b'fixture-target'
    run.before = {'boot_id': saved}
    run.report = {}
    run.pending_read = run.inflight = True
    run.recovery_failed = False
    run.ops, run.tmp = {'verify':'fixture-owner-check'}, '/data/local/tmp/fixture_recovery'
    run.calls, run.saves, run.tick = [], 0, 0
    samples = list(observed) if isinstance(observed, list) else [observed]
    def monotonic():
        run.tick += 31
        return run.tick
    def save():
        run.saves += 1
    def shell(command, **kwargs):
        label = kwargs['label']
        run.calls.append((label, command, kwargs))
        if label == fail_label:
            raise RuntimeError('fixture verification failure')
        if label == 'recovery-boot':
            return samples.pop(0) if len(samples) > 1 else samples[0]
        values = {'recovery-complete':complete, 'identity':IDENTITY, 'root':'0',
            'panel':namespace['c1'].PANEL, 'module':namespace['MODULE_SHA']+'  fixture',
            'recovery-owner':'', 'recovery-dc':'0', 'recovery-esd':'reg_read'}
        if label not in values:
            raise AssertionError('Unexpected device action: '+label)
        return values[label]
    run.monotonic, run.sleep, run.save, run.shell = monotonic, lambda _:None, save, shell
    return run


class ProposedBootGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.proposed = source_pair()
        cls.sweep, cls.namespace = extracted_class(cls.proposed)

    def make(self, observed=AFTER, **kwargs):
        return fixture(self.sweep, self.namespace, observed, **kwargs)

    def one_reboot(self, run):
        requests = [c for c in run.g.calls if c[0] == 'run']
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1], ['adb','-t','7','reboot'])
        self.assertEqual(requests[0][2], {'capture_output':True,'timeout':15})
        self.assertEqual(run.target, 7)
        self.assertEqual([c for c in run.g.calls if c[0]=='wait'], [('wait','fixture-target',90)])

    def rejected(self, run):
        before = dict(run.before)
        with self.assertRaises((RuntimeError, ValueError)):
            run.recover()
        self.one_reboot(run)
        self.assertTrue(run.pending_read and run.inflight and run.recovery_failed)
        self.assertNotIn('recovery_reboot_verified', run.report)
        self.assertEqual(run.before, before)
        count = len(run.calls)
        with self.assertRaises(ValueError):
            run.restore()  # Actual restore's first guard; no settings dispatched.
        self.assertEqual(len(run.calls), count)
        self.assertGreaterEqual(run.saves, 2)

    def test_exact_patch_bound_to_actual_source(self):
        self.assertEqual(self.original.replace(OLD,NEW),self.proposed)
        self.assertEqual(source_pair(), (self.original,self.proposed))

    def test_valid_new_boot_real_identity_and_postchecks(self):
        run=self.make();run.recover();self.one_reboot(run)
        self.assertFalse(run.pending_read or run.inflight or run.recovery_failed)
        self.assertTrue(run.report['recovery_reboot_verified'])
        self.assertEqual(run.before['boot_id'], AFTER)
        self.assertEqual([c[0] for c in run.calls], ['recovery-boot','recovery-complete',
            'identity','root','panel','module','recovery-owner','recovery-dc','recovery-esd'])
        self.assertEqual(run.report['watchdog_state'],'inactive_after_verified_reboot')

    def test_valid_same_boot_never_clears_uncertainty(self):
        self.rejected(self.make(BEFORE))

    def test_invalid_observed_boots(self):
        for value in ('','not-a-uuid',AFTER.upper(),AFTER+'\n'+BEFORE,AFTER+'x',
                      AFTER.replace('-',''), ' '+AFTER, AFTER+'\n'):
            with self.subTest(value=value):
                run=self.make(value);self.rejected(run)
                self.assertNotIn('identity',[c[0] for c in run.calls])

    def test_invalid_saved_boots(self):
        for value in ('','not-a-uuid',AFTER.upper(),BEFORE+'\n'+AFTER,BEFORE+'x',None):
            with self.subTest(value=value):
                if value is None:
                    run=self.make(saved=value)
                    with self.assertRaises(TypeError):run.recover()
                    self.one_reboot(run)
                    self.assertTrue(run.pending_read and run.inflight and run.recovery_failed)
                else:
                    self.rejected(self.make(saved=value))

    def test_both_empty(self):
        self.rejected(self.make('',saved=''))

    def test_incomplete_boot(self):
        for complete in ('','0','2','1\nextra'):
            with self.subTest(complete=complete):
                self.rejected(self.make(complete=complete))

    def test_malformed_then_valid_is_readonly_poll_not_second_reboot(self):
        run=self.make(['not-a-uuid',AFTER]);run.recover();self.one_reboot(run)
        self.assertEqual([c[0] for c in run.calls].count('recovery-boot'),2)
        self.assertEqual(run.before['boot_id'],AFTER)
        self.assertTrue(run.report['recovery_reboot_verified'])

    def test_uncertain_reboot_still_requires_valid_changed_boot(self):
        run=self.make(reboot_error=True);run.recover();self.one_reboot(run)
        self.assertEqual(run.report['reboot_request_error'],'TimeoutError')
        self.assertNotIn('reboot_request_accepted',run.report)
        self.assertTrue(run.report['recovery_reboot_verified'])
        self.rejected(self.make('',reboot_error=True))

    def test_real_postchecks_still_required(self):
        for label in ('identity','root','panel','module','recovery-owner','recovery-dc','recovery-esd'):
            with self.subTest(label=label):
                self.rejected(self.make(fail_label=label))

    def test_baseline_counterexamples_are_real_method_behavior(self):
        original, namespace=extracted_class(self.original)
        for bad in ('','not-a-uuid'):
            with self.subTest(bad=bad):
                run=fixture(original,namespace,bad);run.recover();self.one_reboot(run)
                self.assertTrue(run.report['recovery_reboot_verified'])
                self.assertFalse(run.pending_read or run.inflight)


if __name__ == '__main__':
    unittest.main(verbosity=2)
