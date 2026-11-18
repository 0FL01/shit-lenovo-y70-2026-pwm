"""The archived return flags alone are insufficient evidence of reverse A9."""
import copy
import json
import unittest

from audit import check_history, root


class History(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = root / "artifacts/dsi_coupled_9d_20261107/owner_view"
        cls.original = [json.loads((base / n).read_text()) for n in ("run.json", "return/run.json")]

    def test_archived_pair(self):
        check_history(*self.original)

    def test_changed_fields_rejected(self):
        for path, bad in (
            ((0,"candidate_attempts"), True),
            ((0,"candidate_attempts_by_name"), {"a9_only":1}),
            ((1,"candidate_attempts"), 1),
            ((0,"stages",1,"label"), "a9_only"),
            ((0,"stages",1,"native_packets_matched"), 74),
            ((1,"stages",0,"native_packets_matched"), "75"),
            ((0,"stages",0,"readback","values","23:A9"), [142]),
            ((0,"stages",1,"readback","values","24:9D"), [14]),
            ((0,"stages",1,"readback","values","00:52"), [14,0]),
            ((1,"stages",0,"readback","values","24:9D"), [142]),
            ((1,"stages",0,"readback","esd"), "simulated"),
            ((1,"authorization","program_sha256","stock"), "not the stock program"),
            ((0,"authorization","candidates"), ["a9_only"]),
            ((0,"stages",1,"chunks_verified"), 4),
            ((0,"stages",1,"same_dbv_replay","observed_writes"), []),
            ((1,"stock_return_verified"), False),
            ((1,"pending_bytes_may_exist"), True),
        ):
            with self.subTest(path=path):
                pair = copy.deepcopy(self.original)
                node = pair
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = bad
                with self.assertRaises(ValueError):
                    check_history(*pair)

    def test_swapped_stages(self):
        pair = copy.deepcopy(self.original)
        pair[0]["stages"].reverse()
        with self.assertRaises(ValueError):
            check_history(*pair)


if __name__ == "__main__":
    unittest.main()
