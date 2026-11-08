"""Offline authorization/byte and manual-return regression for S0C1. No ADB."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_dsi_mode_trial as runner


class CoupledOnTests(unittest.TestCase):
    def approval_fixture(self):
        # In-memory TEST fixture, never an authorization record for hardware.
        return {
            'proposal': runner.COUPLED_PROPOSAL, 'candidates': ['s0c1'],
            'sequence': ['stock', 's0c1', 'stock'],
            'program_sha256': dict(runner.COUPLED_HASHES),
            'emergency_reboot_approved': True,
            'owner_confirmation': 'SYNTHETIC OFFLINE TEST ONLY; not owner approval',
            'approved_at_utc': '2026-11-07T00:00:00+00:00',
        }

    def test_exact_native_candidate_and_strict_authorization(self):
        out = runner.ROOT / 'artifacts/dsi_coupled_on_20261107'
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            programs, stages = runner.coupled_on_programs(out, self.approval_fixture())
            self.assertEqual(stages, [('baseline', 'stock'), ('s0c1', 's0c1'), ('return_s0c1', 'stock')])
            self.assertEqual(len(programs['s0c1']), 875)
            self.assertEqual(sum(a != b for a, b in zip(programs['stock'], programs['s0c1'])), 83)
            for key, value in [('proposal', 'wrong'), ('candidates', ['a9_only']),
                               ('sequence', ['s0c1']), ('program_sha256', {}),
                               ('emergency_reboot_approved', False),
                               ('emergency_reboot_approved', 'true'),
                               ('owner_confirmation', ''), ('approved_at_utc', '')]:
                with self.subTest(key=key, value=value):
                    auth = self.approval_fixture()
                    auth[key] = value
                    with self.assertRaises(ValueError):
                        runner.coupled_on_programs(out, auth)
            with tempfile.TemporaryDirectory(dir='/home/stfu/.cache/opencode-tmp/opencode', prefix='s0c1-test-') as directory:
                altered = bytearray(programs['s0c1'])
                altered[68] = 0x8e
                (Path(directory) / 'on_keep_pwm_selectors.bin').write_bytes(altered)
                with self.assertRaisesRegex(ValueError, 'two OFF selectors'):
                    runner.coupled_on_programs(Path(directory), self.approval_fixture())

    def test_missing_authorization_stops_before_device_or_output(self):
        with tempfile.TemporaryDirectory(dir='/home/stfu/.cache/opencode-tmp/opencode', prefix='s0c1-test-') as directory:
            root = Path(directory)
            for option in ('--coupled-on', '--coupled-9d', '--coupled-on-view', '--coupled-on-return'):
                with self.subTest(option=option), \
                     patch.object(runner, 'ROOT', root), \
                     patch.object(runner.sys, 'argv', ['runner', '1', '2', option]), \
                     patch.object(runner.subprocess, 'run') as run, \
                     patch.object(runner.subprocess, 'check_output') as output:
                    with self.assertRaises(FileNotFoundError):
                        runner.main()
                    run.assert_not_called()
                    output.assert_not_called()
                    self.assertEqual(list(root.iterdir()), [])

    def test_return_rejects_invalid_saved_native_dbv_before_device_calls(self):
        with tempfile.TemporaryDirectory(dir='/home/stfu/.cache/opencode-tmp/opencode', prefix='s0c1-test-') as directory:
            root = Path(directory)
            view = root / 'artifacts/dsi_coupled_on_20261107/owner_view'
            view.mkdir(parents=True)
            auth = self.approval_fixture()
            auth['owner_view_approved'] = True
            (view / 'authorization.json').write_text(json.dumps(auth))
            with patch.object(runner, 'ROOT', root), \
                 patch.object(runner.sys, 'argv', ['runner', '1', '0', '--coupled-on-return']), \
                 patch.object(runner.subprocess, 'run') as run:
                for value in ('828', '828; false', -1, 16181):
                    with self.subTest(value=value):
                        (view / 'run.json').write_text(json.dumps({
                            'owner_view_active': True, 'pending_bytes_may_exist': False,
                            'before': {'native_dbv': value},
                        }))
                        with self.assertRaisesRegex(AssertionError, 'Invalid saved native DBV'):
                            runner.main()
                run.assert_not_called()
                self.assertFalse((view / 'return').exists())

    def test_a0d1c1_requires_its_own_scope_and_preserves_on_9d(self):
        out = runner.ROOT / 'artifacts/dsi_coupled_9d_20261107'
        auth = self.approval_fixture()
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('No process allowed')):
            with self.assertRaisesRegex(ValueError, 'Exact coupled proposal'):
                runner.coupled_on_programs(out, auth, keep_9d_on=True)
            auth.update(proposal=runner.COUPLED_9D_PROPOSAL, candidates=['a0d1c1'],
                        sequence=['stock', 'a0d1c1', 'stock'], program_sha256=dict(runner.COUPLED_9D_HASHES))
            programs, stages = runner.coupled_on_programs(out, auth, keep_9d_on=True)
            self.assertEqual(stages, [('baseline', 'stock'), ('a0d1c1', 'a0d1c1'), ('return_a0d1c1', 'stock')])
            self.assertEqual((programs['a0d1c1'][68], programs['a0d1c1'][97]), (0x0e, 0x8e))
            self.assertEqual(sum(a != b for a,b in zip(programs['stock'], programs['a0d1c1'])), 84)
            with self.assertRaisesRegex(ValueError, 'Exact coupled proposal'):
                runner.coupled_on_programs(out, auth)


if __name__ == '__main__':
    unittest.main()
