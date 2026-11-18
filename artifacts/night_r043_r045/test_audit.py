import unittest
from audit import archive, screen

class TestAudit(unittest.TestCase):
    def test_conservative_bounds(self):
        a=archive([[1,2,3],[4,5,6],[2,3,4]], "ABA")
        self.assertEqual(a["B_minus_A_all_slot_range"],[0,5])
        self.assertEqual(a["B_minus_A_median_range"],[2,3])
    def test_bad_archive(self):
        for rows in ([[1,3,2]]*3, [[1,2,3]], [[1,2,float("nan")]]*3):
            with self.assertRaises(ValueError): archive(rows,"ABA")
    def test_numeric_screen(self):
        sham=[[0,1,0]]*3
        for phases,expected in [([1,3,1],True),([3,1,3],True),([0,1,0],False),
            ([0,2,4],False),([0,5,2],False),([1,1,1],False)]:
            self.assertEqual(screen(phases,sham),expected)
    def test_bad_sham(self):
        for sham in ([],[[0,0,0]]*2,[[0,float("inf"),0]]*3):
            with self.assertRaises(ValueError): screen([0,2,0],sham)
if __name__=="__main__": unittest.main()
