import unittest
import audit

class Bands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (audit.BASE/'ddic_regdump_20261107'/audit.STATES[0]/'raw.txt').open() as f:
            cls.r = audit.parse(f)[0]

    def test_report(self):
        actual = audit.run()
        self.assertEqual(actual['adjacent_pairs'],[[3600,3601],[2632,2633],[1920,1921],[1400,1401],[1,2]])
        self.assertEqual(actual['passes'],8)
        self.assertEqual(actual['scoped_prefixes_per_pass'],18)

    def test_one_byte(self):
        for key in self.r:
            with self.subTest(key=key):
                r = dict(self.r)
                p = 2 if key == '53:89' else 0
                data = bytearray(r[key])
                data[p] ^= 1
                r[key] = bytes(data)
                with self.assertRaises(ValueError):
                    audit.inspect(r)

    def test_missing(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            audit.parse([])

    def test_duplicate(self):
        line = 'R 1 24 D2 ' + ' '.join(['00']*40)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            audit.parse([line,line])
