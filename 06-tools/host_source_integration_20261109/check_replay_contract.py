"""Offline future-worktree overlay tests; never writes the runtime checkout."""
import unittest
import difflib
from pathlib import Path
from unittest.mock import patch
import replay_source_fixture as source
import check_future_tree

class ReplayContract(unittest.TestCase):
    def overlay(self,*,corrupt=False,uncomposed=False):
        original=Path.read_bytes
        target={source.ROOT/p:(source.HERE/r['baseline_file' if uncomposed else 'intended_file']).read_bytes()
                for p,r in source.BINDING['four_sources'].items()}
        if corrupt:target[next(iter(target))]+=b'\n'
        def read(path):return target[path] if path in target else original(path)
        return patch.object(Path,'read_bytes',read)
    def test_current_intended_overlay_runs_52_without_transform(self):
        with self.overlay():
            self.assertTrue(check_future_tree.run(current=True))
    def test_archives_reconstruct_exact_reviewed_patch(self):
        text=''
        for p,r in source.BINDING['four_sources'].items():
            old=(source.HERE/r['baseline_file']).read_text()
            new=(source.HERE/r['intended_file']).read_text()
            text+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+p,tofile='b/'+p))
        self.assertEqual(text,(source.HERE/'combined.proposed.patch').read_text())
    def test_baseline_does_not_read_changed_worktree(self):
        expected=source.baseline_inputs()
        with self.overlay(corrupt=True):self.assertEqual(source.baseline_inputs(),expected)
    def test_corrupt_current_fails_before_suite(self):
        with self.overlay(corrupt=True),self.assertRaisesRegex(RuntimeError,'Replay source mismatch'):
            check_future_tree.run(current=True)
    def test_corrupt_archived_baseline_refused(self):
        original=Path.read_bytes
        path=source.HERE/next(iter(source.BINDING['four_sources'].values()))['baseline_file']
        def read(p):return original(p)+(b'\n' if p==path else b'')
        with patch.object(Path,'read_bytes',read),self.assertRaises(RuntimeError):source.baseline_inputs()
    def test_uncomposed_overlay_refuses(self):
        with self.overlay(uncomposed=True),self.assertRaises(RuntimeError):
            source.intended_sources(current=True)
if __name__=='__main__':unittest.main()
