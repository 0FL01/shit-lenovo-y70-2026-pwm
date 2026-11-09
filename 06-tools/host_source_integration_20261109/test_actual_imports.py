"""One isolated subprocess; loads actual bound source bytes, never main."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

class ActualImportTests(unittest.TestCase):
    def test_isolated_actual_sixteen_modules(self):
        script=Path(__file__).with_name('check_actual_imports.py')
        result=subprocess.run([sys.executable,'-I','-B',*(['-O'] if sys.flags.optimize else []),
                               str(script)],capture_output=True,text=True,check=True,timeout=20)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'import_only_pass')
        self.assertEqual(report['modules'],19)
        self.assertFalse(report['tracked_source_admission'])
        self.assertEqual(report['device_services'],0)
        self.assertEqual(report['caller_or_adapter_instances'],0)
        self.assertFalse(report['private_sink_created'])
        self.assertEqual(report['faked_path_resolutions'],['run_dsi_mode_trial.__file__'])

if __name__=='__main__':unittest.main()
