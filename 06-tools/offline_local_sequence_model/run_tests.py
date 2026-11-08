"""Offline unittest runner; prints only synthetic counts, never reads external data."""
import unittest
from model import State, EventKind, Phase

class CountedResult(unittest.TextTestResult):
    subcases = 0
    def addSubTest(self, test, subtest, err):
        self.subcases += 1
        super().addSubTest(test, subtest, err)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName("test_model")
    result = unittest.TextTestRunner(verbosity=2, resultclass=CountedResult).run(suite)
    print("SYNTHETIC_ONLY tests=%d subcases=%d matrix=%d phases=%d failures=%d errors=%d" %
          (result.testsRun, result.subcases, len(State)*len(EventKind), len(Phase),
           len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
