"""Offline arithmetic gate for the fixed screenshot endpoint, not an acquisition tool.

Only qualified frames may become inputs; this module does not verify provenance,
physical gates, camera controls, optical attribution, timestamps or rollback.
"""

# Units: integers in thousandths of the complete fixed ROI, from replay.measure.
# Design margins, not calibrated uncertainty or sensitivity.
DRIFT = 30
EFFECT = 60


def _rows(rows, n):
    if len(rows) != n or any(len(row) != 3 for row in rows):
        raise ValueError("expected three shots per phase and every phase")
    for row in rows:
        if any(type(x) is not int or not 0 <= x <= 1000 for x in row):
            raise ValueError("use integer permille, not raw fractions or missing values")


def sham_ok(sham):
    _rows(sham, 3)
    v = [x for row in sham for x in row]
    return max(v) - min(v) <= DRIFT


def classify(sham, aba):
    if not sham_ok(sham):
        return "STOP_SHAM"
    _rows(aba, 3)
    a, b, c = aba
    # All OFF observations must fit a single sham-sized envelope.
    off = [x for row in [*sham, a, c] for x in row]
    if max(off) - min(off) > DRIFT or max(b) - min(b) > DRIFT:
        return "INCONCLUSIVE_DRIFT"
    # Compare nearest edges, not just phase medians; strictly outside margin.
    if min(b) - max(off) > EFFECT or min(off) - max(b) > EFFECT:
        return "CANDIDATE_RASTER_ONLY"
    return "NOT_SEPARATED"
