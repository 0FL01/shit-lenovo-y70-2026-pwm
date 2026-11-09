import hashlib
import unittest
from source_binding_fixture import *

class SourceBindingTests(unittest.TestCase):
    def test_baseline_13_unchanged(self):
        self.assertEqual(len(baseline_sources()), 13)
    def test_original_clean_guard_accepts(self):
        result = original_guard(GitFixture())(root='/fixture', require_clean=True)
        self.assertTrue(result['source_worktree_clean_for_runner'])
        self.assertEqual(len(result['source_blob_ids']),13)
    def test_untracked_or_missing_refused(self):
        with self.assertRaises(RuntimeError):
            original_guard(GitFixture(missing=True))(root='/fixture', require_clean=True)
    def test_changed_worktree_refused(self):
        with self.assertRaises(RuntimeError):
            original_guard(GitFixture(changed=True))(root='/fixture', require_clean=True)
    def test_diff_dirty_refused(self):
        with self.assertRaises(RuntimeError):
            original_guard(GitFixture(diff=1))(root='/fixture', require_clean=True)
    def test_diff_failure_refused(self):
        with self.assertRaises(RuntimeError):
            original_guard(GitFixture(diff=128))(root='/fixture', require_clean=True)
    def test_invalid_commit_refused(self):
        with self.assertRaises(RuntimeError):
            original_guard(GitFixture(commit='invalid'))(root='/fixture', require_clean=True)
    def test_offline_reports_dirty_not_admitted(self):
        result=original_guard(GitFixture(missing=True))(root='/fixture',require_clean=False)
        self.assertFalse(result['source_worktree_clean_for_runner'])
    def test_guard_uses_exact_original_paths(self):
        fixture=GitFixture()
        original_guard(fixture)(root='/fixture',require_clean=True)
        self.assertEqual(fixture.calls[-1][0][3:],
                         ['diff','--quiet','a'*40,'--',*BINDING['baseline_paths']])
    def test_virtual_binding(self):
        for item in BINDING['virtual_proposals']:
            raw=baseline_sources()[item['path']]
            virtual=virtual_replace(raw,item['old'],item['new'],item['original_sha256'],
                                    item['virtual_sha256'])
            self.assertEqual(sha(virtual),item['virtual_sha256'])
            compile(virtual,item['path'],'exec') # compilation only
    def test_virtual_wrong_original_refused(self):
        item=BINDING['virtual_proposals'][0]
        with self.assertRaises(RuntimeError):
            virtual_replace(b'changed',item['old'],item['new'],item['original_sha256'],
                            item['virtual_sha256'])
    def test_virtual_wrong_output_refused(self):
        item=BINDING['virtual_proposals'][0]
        with self.assertRaises(RuntimeError):
            virtual_replace(baseline_sources()[item['path']],item['old'],item['new'],
                            item['original_sha256'],'0'*64)
    def test_virtual_nonunique_refused(self):
        raw=b'xx'
        with self.assertRaises(RuntimeError):
            virtual_replace(raw,'x','y',sha(raw),sha(b'yy'))
    def test_reviewed_dependencies_unchanged(self):
        for path,pin in BINDING['reviewed_dependencies_sha256'].items():
            self.assertEqual(sha((ROOT/path).read_bytes()),pin)
    def test_virtual_is_never_clean_admission(self):
        self.assertIs(BINDING['live_admitted'],False)
        self.assertIs(BINDING['runtime_edits'],False)

if __name__ == '__main__': unittest.main()
