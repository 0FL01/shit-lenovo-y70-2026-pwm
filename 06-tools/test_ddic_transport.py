"""Offline regression for CRC/ideal 40-byte reconstruction; no device imports."""
import unittest

from analyze_ddic_transport import crc16, model_read40, prefix_crc_matches


class DDICTransportTests(unittest.TestCase):
    def test_crc_and_conditional_long_read(self):
        self.assertEqual(crc16(b'\x00'), 0x0f87)
        self.assertEqual(crc16(b'123456789'), 0x6f91)
        for payload in (bytes(range(40)), bytes(40), bytes.fromhex('000065')+bytes(37)):
            self.assertEqual(model_read40(payload), payload)
        # The repeated-read helper can cross the requested allocation BEFORE
        # the final parser bounds check. This is not a safe kernel refusal.
        for size in range(1, 11):
            with self.assertRaises(BufferError):
                model_read40(bytes(range(size)))
        for size in range(11, 40):
            short = bytes(range(size))
            copied = model_read40(short)
            expected = (short + crc16(short).to_bytes(2, 'little') + bytes(max(0, 38-size)))[:40]
            self.assertEqual(copied, expected, f'fixed payload length {size}')
        self.assertIn(11, prefix_crc_matches(model_read40(bytes(range(11)))))
        c1 = bytes.fromhex('000065')+bytes(37)
        self.assertEqual(prefix_crc_matches(c1), [])
        # A length2 coincidence embedded in longer data is NOT a trailer proof.
        coincident = bytes.fromhex('9aa6a9d47118a7bda687920c7f18117d')+bytes(24)
        self.assertEqual(prefix_crc_matches(coincident), [2])
        for bad in (b'', bytes(41)):
            with self.assertRaises(ValueError):
                model_read40(bad)


if __name__ == '__main__':
    unittest.main()
