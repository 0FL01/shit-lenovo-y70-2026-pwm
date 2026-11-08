import pathlib
import unittest
import p85_single_bit_plan as p

class PlanTests(unittest.TestCase):
    def test_exact(self):
        for stage, value in [('candidate14', 20), ('restore15', 21)]:
            packets = p.proposal(stage)
            self.assertEqual(packets[1], bytes.fromhex('39 00 00 00 00 00 02 85') + bytes([value]))
            self.assertFalse(p.validate_program(packets, stage)['execution_approved'])
    def test_one_bit(self):
        a, b = p.proposal('candidate14'), p.proposal('restore15')
        self.assertEqual(sum((x ^ y).bit_count() for x,y in zip(b''.join(a), b''.join(b))), 1)
    def test_no_other_values(self):
        for stage in ['candidate11', 'stock', 20, None, True]:
            with self.assertRaises(ValueError): p.proposal(stage)
    def test_every_byte_mutation(self):
        original = p.proposal('candidate14')
        for i, packet in enumerate(original):
            for j in range(len(packet)):
                altered = list(original); b = bytearray(packet); b[j] ^= 1; altered[i] = bytes(b)
                with self.assertRaises(ValueError): p.validate_program(tuple(altered), 'candidate14')
    def test_missing_extra_reorder(self):
        a=p.proposal('candidate14')
        for invalid in [a[:2], a+a[:1], a[::-1], list(a), (b''.join(a),)]:
            with self.assertRaises(ValueError): p.validate_program(invalid, 'candidate14')
    def test_callback_delta(self):
        e=[(0,11,0),(0,9,0),(0,11,0)]
        self.assertTrue(p.validate_callback_delta(e,[0]*3,[0]*3))
        for bad in [[(1,11,0)]+e[1:],[(0,11,64)]+e[1:],e[:-1]]:
            with self.assertRaises(ValueError): p.validate_callback_delta(bad,[0]*3,[0]*3)
        for bad in [[0,3,0],[0,-1,0],[0]*4]:
            with self.assertRaises(ValueError): p.validate_callback_delta(e,[0]*3,bad)
    def test_fixture(self):
        root=pathlib.Path(__file__).resolve().parents[1]
        data=(root/'artifacts/device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings/timing@0/qcom,mdss-dsi-on-command').read_bytes()
        self.assertEqual(p.validate_init(data)['write_offset'],310)
        for invalid in [data[:-1],data+data,data[:318]+b'\x14'+data[319:]]:
            with self.assertRaises(ValueError): p.validate_init(invalid)

if __name__ == '__main__': unittest.main()
