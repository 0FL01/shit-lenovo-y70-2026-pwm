import math
import unittest

from audit import NODE, run, scale_interval, selected


class Timing(unittest.TestCase):
    def test_missing(self):
        for args in ((None,(1,2),1),((1,2),None,1),((1,2),(1,2),None)):
            self.assertIsNone(scale_interval(*args))

    def test_endpoint_bound(self):
        self.assertEqual(scale_interval((90,110),(8,10),10), [8,15])
        self.assertEqual(scale_interval((10,10),(2,2),0), [5,5])
        self.assertEqual(scale_interval((9,10),(2,2),10), [0,10])

    def test_invalid(self):
        for args in (((1,2),(0,2),1),((2,1),(1,2),1),((1,2),(1,2),-1),
                     ((1,2),(1,math.inf),1),((math.nan,2),(1,2),0)):
            with self.assertRaises(ValueError):
                scale_interval(*args)


class Archive(unittest.TestCase):
    def test_no_substring_or_duplicate_match(self):
        for rows in ([{'name':NODE+'0'}], [{'name':NODE},{'name':NODE}]):
            with self.assertRaises(ValueError):
                selected(rows,NODE)

    def test_versions_and_scope(self):
        report = run()
        self.assertEqual(report['command_properties'],53)
        self.assertEqual([r[-1] for r in report['reference_rows_model_region_build_equal']], [41,53,53])
        self.assertEqual(len(report['bytes_rechecked_paths']),12)
        self.assertNotIn(NODE,report['excluded_nodes_with_number_of_changed_commands_vs_global'])
        self.assertEqual(len(report['excluded_nodes_with_number_of_changed_commands_vs_global']),8)

    def test_no_physical_transfer(self):
        report = run()
        self.assertEqual(report['camera_reentry_pairs_scored'],0)
        self.assertEqual(set(report['synthetic_indistinguishable_us_per_px']),{208,156})
        self.assertIsNone(report['physical_us_per_px'])
        self.assertIsNone(report['physical_pwm_hz'])
