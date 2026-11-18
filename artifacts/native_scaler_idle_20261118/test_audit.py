import unittest
from unittest.mock import patch

import audit


class AuditTest(unittest.TestCase):
    def test_real_release_and_target(self):
        result = audit.audit()
        self.assertEqual(8, len(result['parent_pairs']))
        self.assertTrue(all(len(row[k]['changed_indices']) == 4 for row in result['parent_pairs'] for k in audit.KINDS))
        offsets = result['selected_target']['command_comparison_0_6_7']
        self.assertEqual({'size':1176, 'packets':95, 'byte_offset':840}, offsets['on-command'])
        self.assertEqual({'size':140, 'packets':14, 'byte_offset':48}, offsets['timing-switch-command'])
        self.assertIsNone(result['physical_pwm_hz'])

    def test_truncated_and_empty_descriptor(self):
        for b in (b'', b'\x39\x00', b'\x39\0\0\0\0\0\2\x83', b'\x39'+b'\0'*6):
            with self.subTest(b=b), self.assertRaises(ValueError):
                audit.packets(b)

    def test_duplicate_nodes_and_properties(self):
        with self.assertRaises(ValueError):
            audit.nodes('timing@1{ }; timing@1 { };')
        with self.assertRaises(ValueError):
            audit.prop('qcom,mdss-dsi-x=<1>;qcom,mdss-dsi-x=<2>;', 'x', r'<(\d+)>')

    def test_foreign_changes_are_rejected(self):
        rows = audit.nodes(audit.source('parent'))
        a,b = [audit.command(rows[i],'on-command') for i in (0,8)]
        p,h,x = b[0]
        for entry in ((p,b'\xff'+h[1:],x), (p,h,bytes([x[0]^1])+x[1:]), (p,h,x[:-1]+b'\x06')):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                audit.matched(a,[entry]+b[1:])
        with self.assertRaises(ValueError):
            audit.matched(a,b[:-1])

    def test_wrong_source_identity_is_rejected(self):
        with patch.dict(audit.BLOBS, {'parent':'0'*40}), self.assertRaisesRegex(ValueError,'identity'):
            audit.source('parent')


if __name__ == '__main__':
    unittest.main()
