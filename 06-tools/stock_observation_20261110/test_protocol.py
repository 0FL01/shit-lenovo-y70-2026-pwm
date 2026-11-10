"""Offline fault skeleton; does not simulate a proven hardware stop."""
import unittest
from protocol import Budget, validate_timeline


def armed():
    b = Budget()
    b.arm(**dict.fromkeys(('preview_verified', 'local_stop_verified',
                          'roles_verified', 'originals_bound', 'source_bound',
                          'mutex_owned'), True))
    return b


class Tests(unittest.TestCase):
    def test_missing_local_stop(self):
        b = Budget()
        with self.assertRaises(ValueError):
            b.arm(preview_verified=True, local_stop_verified=False,
                  roles_verified=True, originals_bound=True, source_bound=True,
                  mutex_owned=True)

    def test_budget_includes_startup(self):
        b = armed(); b.attempt_start(100); b.observed_recording(108)
        self.assertEqual(b.remaining(108), 7)
        b.observed_recording(115)
        self.assertEqual(b.failure, 'recording_at_deadline')

    def test_uncertain_start_no_retry(self):
        b = armed(); b.attempt_start(0); b.fail('network_at_start')
        with self.assertRaises(ValueError): b.attempt_start(1)
        self.assertEqual(b.stop_action(fresh_ui_state='unknown'), 'retain_uncertainty_no_tap')

    def test_already_stopped_not_toggled(self):
        b = armed(); b.attempt_start(0)
        self.assertEqual(b.stop_action(fresh_ui_state='preview'), 'verify_preview_without_tap')
        receipt = b.observed_preview(20)
        self.assertFalse(receipt['timely_stop_proven_by_host'])
        with self.assertRaises(ValueError): b.stop_action(fresh_ui_state='preview')

    def test_network_at_stop_retains_failure(self):
        b = armed(); b.attempt_start(0); b.observed_recording(1)
        self.assertEqual(b.stop_action(fresh_ui_state='recording'), 'verified_stop_control_once')
        self.assertEqual(b.stop_action(fresh_ui_state='recording'), 'retain_uncertainty_no_tap')
        b.fail('network_at_stop'); b.observed_preview(17)
        self.assertEqual(b.failure, 'network_at_stop')

    def test_clock_invalid(self):
        b = armed(); b.attempt_start(10)
        for now in (9, float('nan'), True):
            with self.assertRaises(ValueError): b.remaining(now)

    def test_exact_windows(self):
        self.assertEqual(validate_timeline([i/30 for i in range(390)],
                         encoded_duration=13, early_controls_bound=True)[-1], (300, 360))

    def test_timeline_faults(self):
        good = [i/30 for i in range(390)]
        bad = good.copy(); bad[90] += .01
        cases = [(good, 15.01, True), (good[:359], 13, True),
                 (bad, 13, True), (good, 13, False), (good, 12, True)]
        for pts, duration, controls in cases:
            with self.subTest(duration=duration, controls=controls, n=len(pts)):
                with self.assertRaises(ValueError):
                    validate_timeline(pts, encoded_duration=duration,
                                      early_controls_bound=controls)


if __name__ == '__main__':
    unittest.main()
