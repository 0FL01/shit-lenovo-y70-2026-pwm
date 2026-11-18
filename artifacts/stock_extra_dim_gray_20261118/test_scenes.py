import base64
import unittest

from scenes import CODES, PLAN, data_url, gray_candidates, page


class Scenes(unittest.TestCase):
    def test_candidate_models(self):
        self.assertEqual(gray_candidates(), (191, 133))
        self.assertEqual(gray_candidates(0), (0, 0))
        self.assertEqual(gray_candidates(1), (255, 255))
        with self.assertRaises(ValueError):
            gray_candidates(-0.1)

    def test_same_markup_except_channels(self):
        baseline = page(255).replace('255,255,255', '<rgb>')
        for code in CODES:
            rgb = ','.join(3 * [str(code)])
            html = page(code)
            self.assertEqual(html.count(rgb), 1)
            self.assertEqual(html.replace(rgb, '<rgb>'), baseline)
            self.assertNotIn('script', html)
            self.assertEqual(base64.b64decode(data_url(code).split(',', 1)[1]).decode(), html)

    def test_sham_and_returns(self):
        self.assertEqual(len(PLAN), 8)
        self.assertEqual(PLAN[1][1:], PLAN[2][1:])
        self.assertEqual(PLAN[0][1:], PLAN[-1][1:])
        self.assertEqual([code for _, code, active in PLAN if code != 255 and not active], [191, 133])
        with self.assertRaises(ValueError):
            page(200)


if __name__ == '__main__':
    unittest.main()
