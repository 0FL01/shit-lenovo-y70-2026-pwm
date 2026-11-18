import unittest
from audit import reverse_windows

class Windows(unittest.TestCase):
    def test_overlap_is_not_replication(self):
        d = reverse_windows("ABABA", [2, 0, 3, 1, 4])
        self.assertEqual(d["disjoint_ABA_BAB_pairs"], 0)
        self.assertEqual([w["B_minus_A"] for w in d["windows"]], [[-2,-3],[-3,-2],[-2,-3]])
        self.assertEqual(d["AAA_windows"], 0)
    def test_disjoint_is_only_an_index_property(self):
        self.assertEqual(reverse_windows("ABABAB", [1,2]*3)["disjoint_ABA_BAB_pairs"], 1)
    def test_sham_overlaps_count_as_windows_only(self):
        self.assertEqual(reverse_windows("AAAAB", [1]*5)["AAA_windows"], 2)
    def test_invalid(self):
        for seq, vals in (("ABA", [1,2]), ("ABA", [1,float("nan"),2]), ("ACA", [1,2,3])):
            with self.assertRaises(ValueError):
                reverse_windows(seq, vals)
