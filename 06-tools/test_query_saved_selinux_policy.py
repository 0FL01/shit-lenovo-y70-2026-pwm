#!/usr/bin/env python3
"""Focused subprocess tests; no generated fixtures and no device access."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '06-tools/query_saved_selinux_policy.py'
POLICY = ROOT / 'extracted/XT2611-1/W3WWL36.65-11-18/filesystems/odm_a/etc/selinux/precompiled_sepolicy'

class SavedPolicyTests(unittest.TestCase):
    def run_query(self, policy=POLICY, source='u:r:shell:s0', klass='dir', permission='write'):
        return subprocess.run(['python3', str(SCRIPT), str(policy), '--source-context', source,
            '--target-context', 'u:object_r:system_data_file:s0', '--class-name', klass,
            '--permissions', permission], capture_output=True, text=True, timeout=20)

    def test_cn_write_and_search(self):
        for permission, expected in [('write', False), ('search', True)]:
            r = self.run_query(permission=permission)
            self.assertEqual(r.returncode, 0, r.stderr)
            result = json.loads(r.stdout)['results'][0]
            self.assertEqual(result['allowed'], expected)
            if permission == 'write':
                self.assertTrue(result['denied_and_audit_suppressed'])

    def test_invalid_policy(self):
        r = self.run_query(policy=SCRIPT)
        self.assertEqual(r.returncode, 1)
        self.assertIn('parse supplied policy', r.stderr)

    def test_invalid_context(self):
        r = self.run_query(source='u:r:nonexistent_query_test_type:s0')
        self.assertEqual(r.returncode, 1)
        self.assertIn('source context', r.stderr)

    def test_invalid_class(self):
        r = self.run_query(klass='nonexistent_query_test_class')
        self.assertEqual(r.returncode, 1)
        self.assertIn('class lookup', r.stderr)

    def test_invalid_permission(self):
        r = self.run_query(permission='nonexistent_query_test_permission')
        self.assertEqual(r.returncode, 1)
        self.assertIn('permission lookup', r.stderr)

    def test_ascii_bounds(self):
        r = self.run_query(source='x' * 513)
        self.assertEqual(r.returncode, 1)
        self.assertIn('bounded ASCII', r.stderr)

if __name__ == '__main__':
    unittest.main(verbosity=2)
