"""Explicit post-application regression route, fake I/O and virtual Git only.

Default uses frozen intended4 overlay. --current reads actual intended tree and
fails closed on original bytes. Neither mode is source-clean admission.
"""
import argparse
import importlib
import sys
import unittest
from unittest.mock import patch
import combined_fixture as fixture
from replay_source_fixture import baseline_inputs,intended_sources

def run(*,current=False):
    baseline=baseline_inputs()
    intended=intended_sources(current=current)
    # No proposal.sources(), patch transform or original-path imports in this route.
    # Original fixtures use baseline only for explicit negative uncomposed case.
    def sources():return dict(baseline)
    def composed(_):return dict(intended)
    suite=unittest.TestSuite()
    omitted='test_actual_current_untracked_tree_blocks_before_mkdir_transport'
    with patch.object(fixture,'inputs',sources),patch.object(fixture,'compose',composed):
        for name in ('test_combined_integration','test_host_entrypoint'):
            module=importlib.import_module(name)
            for cls in (getattr(module,'CombinedTests',None),getattr(module,'EntryTests',None)):
                if cls:
                    for method in unittest.defaultTestLoader.getTestCaseNames(cls):
                        if method!=omitted:suite.addTest(cls(method))
        result=unittest.TextTestRunner(verbosity=1).run(suite)
    if result.testsRun!=52:raise RuntimeError('Post-application suite count changed')
    return result.wasSuccessful()
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current',action='store_true')
    args=parser.parse_args()
    sys.exit(0 if run(current=args.current) else 1)
