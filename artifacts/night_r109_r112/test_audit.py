import csv
import json
import unittest
from pathlib import Path

from audit import score, MATRIX


class TestScore(unittest.TestCase):
    def setUp(self):
        with MATRIX.open(newline='') as f:
            self.rows = list(csv.DictReader(f))

    def test_archived_replay_and_singleton(self):
        got = score(self.rows)
        self.assertEqual(got, json.loads(Path(__file__).with_name('result.json').read_text()))
        self.assertEqual([x for x, verdict in got.items() if verdict['separated']], ['3600:0'])
        self.assertEqual(got['3600:0']['worst_gap'], '0.294167')

    def test_identical_matrix_is_not_distinguished(self):
        for row in self.rows:
            row.update(Dmin='0', Dmed='0', Dmax='0')
        self.assertFalse(any(x['separated'] for x in score(self.rows).values()))

    def test_tie_within_self_counts_against_anchor(self):
        for row in self.rows:
            if row['dbv_dc_a'] == row['dbv_dc_b'] == '3600:0':
                row['Dmax'] = '1'
        self.assertFalse(score(self.rows)['3600:0']['separated'])

    def test_missing_duplicate_wrong_count_and_bad_bounds(self):
        for altered in (self.rows[:-1], self.rows + self.rows[:1],
                        [{**self.rows[0], 'n': '14'}]+self.rows[1:],
                        [{**self.rows[0], 'Dmax': '0'}]+self.rows[1:]):
            with self.subTest(), self.assertRaises(ValueError):
                score(altered)

    def test_invariant_to_row_order_and_pair_orientation(self):
        rows = [{**r, 'dbv_dc_a': r['dbv_dc_b'], 'dbv_dc_b': r['dbv_dc_a']}
                for r in reversed(self.rows)]
        self.assertEqual(score(rows), score(self.rows))
