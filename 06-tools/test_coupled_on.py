"""Offline authorization/byte and manual-return regression for S0C1. No ADB."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_dsi_mode_trial as runner

CACHE = Path.home() / '.cache/opencode-tmp/opencode'


class CoupledOnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CACHE.mkdir(parents=True, exist_ok=True)

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
            with tempfile.TemporaryDirectory(dir=CACHE, prefix='s0c1-test-') as directory:
                altered = bytearray(programs['s0c1'])
                altered[68] = 0x8e
                (Path(directory) / 'on_keep_pwm_selectors.bin').write_bytes(altered)
                with self.assertRaisesRegex(ValueError, 'two OFF selectors'):
                    runner.coupled_on_programs(Path(directory), self.approval_fixture())

    def test_missing_authorization_stops_before_device_or_output(self):
        with tempfile.TemporaryDirectory(dir=CACHE, prefix='s0c1-test-') as directory:
            root = Path(directory)
            for option in ('--coupled-on', '--coupled-9d', '--coupled-on-view', '--coupled-on-return',
                           '--coupled-9d-view', '--coupled-9d-return'):
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
        with tempfile.TemporaryDirectory(dir=CACHE, prefix='s0c1-test-') as directory:
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

    def test_a0d1c1_manual_return_checks_saved_view_before_device_calls(self):
        with tempfile.TemporaryDirectory(dir=CACHE, prefix='a0d1c1-test-') as directory:
            root = Path(directory)
            view = root / 'artifacts/dsi_coupled_9d_20261107/owner_view'
            view.mkdir(parents=True)
            auth = self.approval_fixture()
            auth.update(proposal=runner.COUPLED_9D_PROPOSAL, candidates=['a0d1c1'],
                        sequence=['stock', 'a0d1c1', 'stock'], program_sha256=dict(runner.COUPLED_9D_HASHES),
                        owner_view_approved=True)
            (view / 'authorization.json').write_text(json.dumps(auth))
            (view / 'run.json').write_text(json.dumps({
                'owner_view_active': True, 'pending_bytes_may_exist': False,
                'before': {'native_dbv': 16181},
            }))
            with patch.object(runner, 'ROOT', root), \
                 patch.object(runner.sys, 'argv', ['runner', '1', '0', '--coupled-9d-return']), \
                 patch.object(runner.subprocess, 'run') as run:
                with self.assertRaisesRegex(AssertionError, 'Invalid saved native DBV'):
                    runner.main()
                run.assert_not_called()
                self.assertFalse((view / 'return').exists())

    def test_reboot_wait_binds_target_serial_with_two_phones(self):
        target = 'SYNTHETIC_TARGET'
        phones = ('List of devices attached\n'
                  'SYNTHETIC_CAMERA device model:moto_g54_5G device:cancunf transport_id:3\n'
                  'SYNTHETIC_TARGET device model:motorola_edge_70_max device:avr transport_id:12\n')
        with patch.object(runner.subprocess, 'run', side_effect=[
            runner.subprocess.CompletedProcess([], 0, b'', b''),
            runner.subprocess.CompletedProcess([], 0, phones, ''),
        ]) as run:
            self.assertEqual(runner.wait_for_rebooted_target(target), 12)
            self.assertEqual(run.call_args_list[0].args[0], ['adb', '-s', target, 'wait-for-device'])
        with patch.object(runner.subprocess, 'run', side_effect=[
            runner.subprocess.CompletedProcess([], 0, b'', b''),
            runner.subprocess.CompletedProcess([], 0, phones.replace('SYNTHETIC_TARGET', 'OTHER_TARGET'), ''),
        ]):
            with self.assertRaisesRegex(RuntimeError, 'Cannot independently select returned target'):
                runner.wait_for_rebooted_target(target)

    def test_a001_video_selection_uses_unique_new_file_not_host_time(self):
        old = '/sdcard/DCIM/OpenCamera/existing.mp4'
        new = '/sdcard/DCIM/OpenCamera/a001_recording.mp4'
        self.assertEqual(runner.new_camera_video(old, old + '\n' + new), new)
        for before, after in ((old, old), (old, new), (old, old + '\n' + new + '\n' + new),
                              (old, old + '\n/sdcard/DCIM/OpenCamera/../escape.mp4'),
                              (old, old + '\n' + new + '\n/sdcard/DCIM/OpenCamera/second.mp4')):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                runner.new_camera_video(before, after)


if __name__ == '__main__':
    unittest.main()
