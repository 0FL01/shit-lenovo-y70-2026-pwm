import hashlib
import ast
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import prestart_inspection as v1
import prestart_inspection_v2 as v2
import test_prestart_inspection as fixtures
import probe

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.saved = patch.dict(sys.modules); self.saved.start()
        for name in probe.SOURCES:
            sys.modules.pop(name, None)
    def tearDown(self):
        self.saved.stop()
    def context(self):
        return fixtures.InspectionTests().context()
    def failure(self, context):
        with self.assertRaises(v2.InspectionFailure) as caught:
            v2.inspect(**context)
        value = caught.exception.diagnostics
        self.assertFalse(value['capture_admitted'])
        for private in ('target-private', 'camera-private', 'PRIVATE_SECRET', 'session_token'):
            self.assertNotIn(private, json.dumps(value))
        self.assertEqual(value['receipt_phase'], 'final')
        return value

    def test_original_failed_helper_preserved(self):
        self.assertEqual(hashlib.sha256(Path(v1.__file__).read_bytes()).hexdigest(),
            '5af512cf02640e0813e627d9967439bcc1ed5ef334485f1d53cb73000158c723')
        self.assertEqual(v2.CHILD, 'prestart-inspection-v2')
        self.assertEqual(dict(v1.COMMANDS), dict(v2.COMMANDS))
        self.assertEqual(dict(v1.PARSER_SOURCES), dict(v2.PARSER_SOURCES))
        def functions(module):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(Path(module.__file__).read_text()).body
                    if isinstance(n, ast.FunctionDef)}
        before, after = functions(v1), functions(v2)
        for name in ('png_info', 'preview', 'scene', 'validate_native_scene', 'extracted_parser', 'prepare'):
            self.assertEqual(before[name], after[name], name)

    def test_native_parse_code_before_any_png(self):
        ctx = self.context(); ctx['adapter'].extra['native'] = 'PRIVATE_SECRET no anchor'
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (32, 1))
        self.assertEqual(result['last_shell_stage_code'], 31)
        self.assertEqual(result['stdout_bytes'], len('PRIVATE_SECRET no anchor'))
        self.assertEqual(set(ctx['sink'].files), {'failure.json'})
        self.assertTrue(result['failure_receipt_written'])
        disk = json.loads(ctx['sink'].files['failure.json'])
        self.assertEqual(disk['receipt_phase'], 'before_descriptor_close')
        self.assertNotIn('PRIVATE_SECRET', json.dumps(disk))

    def test_software_parse_code(self):
        ctx = self.context(); ctx['adapter'].extra['software'] = 'PRIVATE_SECRET'
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (34, 1))

    def test_camera_parse_distinguished_from_baseline(self):
        ctx = self.context(); original = ctx['adapter'].shell
        def shell(tid, command, timeout):
            if command == v2.COMMANDS['metadata']:
                return 0, b'PRIVATE_SECRET', b''
            return original(tid, command, timeout)
        ctx['adapter'].shell = shell
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (41, 5))

    def test_first_png_invalid_stage_and_sizes(self):
        ctx = self.context(); original = ctx['adapter'].shell
        def shell(tid, command, timeout):
            if command == 'screencap -p':
                return 0, b'PRIVATE_SECRET', b''
            return original(tid, command, timeout)
        ctx['adapter'].shell = shell
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (51, 1))
        self.assertEqual(result['shell_rc'], 0)
        self.assertEqual(result['stdout_bytes'], len(b'PRIVATE_SECRET'))
        self.assertEqual(set(ctx['sink'].files), {'failure.json'})

    def test_baseline_read_has_fixed_role_operation_code(self):
        ctx = self.context(); ctx['adapter'].responses['root'] = '2000'
        result = self.failure(ctx)
        self.assertEqual(result['stage_code'], 106)
        self.assertEqual(result['shell_rc'], 0)
        self.assertEqual(result['stdout_bytes'], 4)
        self.assertEqual(set(ctx['sink'].files), {'failure.json'})

    def test_timeout_no_retry_and_no_raw_exception(self):
        ctx = self.context(); original = ctx['adapter'].shell; attempts = 0
        def shell(tid, command, timeout):
            nonlocal attempts
            if command == v2.COMMANDS['native']:
                attempts += 1
                raise TimeoutError('PRIVATE_SECRET')
            return original(tid, command, timeout)
        ctx['adapter'].shell = shell
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (31, 4))
        self.assertIsNone(result['stdout_bytes'])
        self.assertEqual(attempts, 1)

    def test_success_preserves_existing_guards_and_private_custody(self):
        ctx = self.context(); result = v2.inspect(**ctx)
        self.assertEqual(result['status'], 'prestart_inspected')
        self.assertFalse(result['capture_admitted'])
        self.assertTrue(result['host_cleanup_verified'])
        self.assertEqual(set(ctx['sink'].files), {'target.png', 'camera.png', 'inspection.json'})

    def test_failed_host_open_has_stage_without_receipt(self):
        ctx = self.context()
        ctx['sink'].open = lambda: (_ for _ in ()).throw(OSError('PRIVATE_SECRET'))
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (10, 3))
        self.assertFalse(result['failure_receipt_written'])
        self.assertEqual(ctx['adapter'].calls, [])

    def test_final_close_failure_sticky_and_never_retried(self):
        ctx = self.context(); calls = 0
        def close():
            nonlocal calls
            calls += 1
            ctx['sink'].closed = True
            if calls == 1:
                raise OSError('PRIVATE_SECRET')
            # Models the original consumed-fd/no-op second-close trap.
        ctx['sink'].close = close
        result = self.failure(ctx)
        self.assertEqual((result['stage_code'], result['reason_code']), (91, 3))
        self.assertFalse(result['host_cleanup_verified'])
        self.assertEqual(calls, 1)
        self.assertFalse(result['failure_receipt_written'])
        self.assertEqual(set(ctx['sink'].files), {'target.png', 'camera.png', 'inspection.json'})

if __name__ == '__main__':
    unittest.main()
