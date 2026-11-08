# Inert model freeze, 2026-11-08

Only 06-tools/offline_local_sequence_model/ is written. No device, transport,
producer, private corpus, runtime edit, installation, commit or push.

Python 3.13.5 on nc-lab. Normal and -O runs both pass:
- 16 unittest methods.
- 927 named subcases per run (includes 572 canonical state/event pairs).
- 5 active phase enums, 22 state enums, 26 event enums.
- 0 failures, 0 errors.
- results-normal.txt and results-optimized.txt contain sanitized output.

Frozen source Git blob identities (hash-object, not a commit):
- model.py: e6424d705900bc35337174539e1912b4d12af058
- test_model.py: cd748d9773e05c00d7d55a857f1b39bfb8f59ae8
- run_tests.py: 2cb34ed2d2110c6bad2946c585204d85df45dc41
- README.md: 0a6d2026867e9f412acb3084a7216802eb696c6c
- authoritative design: baf374e23fc2e7b57f7b3ca2a6d660dfe8c618e4

A first test run had a syntax typo in a budget fixture; corrected before counts.
The matrix then found DISCONNECT after a clean terminal incorrectly adding a camera
obligation while retaining that terminal. It now refuses post-terminal disconnect.
This is a useful finite-model counterexample, not a finding about hardware.
Self-review added exact bounded Decimal arithmetic to GUARD_TIMING; a regression
rejects a large decimal delta of 9 that float would round to zero. Independent review
supplied the opposite rounding example, begin536870904.00000007/end536870912.00000007.
Acceptance now requires BOTH exact and inherited float bounds, preserving a strict
conservative subset. Model numeric/enum/flag fixtures have negative checks.
The lead flagged catch-and-continue after reducer exceptions. Public Model is now a
one-shot cursor with atomic sticky failure handling and a shared synthetic Ledger.
60 dedicated public API subcases cover malformed/reordered input at every phase's
reserved/dispatched/produced/sealed checkpoint; repaired SUCCESS cannot resume.
Private immutable reducer snapshots are only independent synthetic test worlds.
Independent review then found three public-cursor invariant gaps: late malformed
camera input could retain a clean terminal with optics_invalid; pre-start quiet
could satisfy normal in-hold quiet; and historical recovery/cleanup receipts could
be replayed after a new audit rejection. These are fixed with degraded terminal
invalidation, start-reset quiet, incident/current-boot/proof binding and one-shot
cleanup per incident. Exact reproductions and neighboring public-API cases cover
both policies and all five cleanup obligations. Historical child receipts remain
immutable, but do not stand for new resource-generation completions.
GUARD_TIMING now requires decimal points in both operands, matching inherited
grammar, with explicit integer/mixed-form negatives and both numeric predicates.
RECONNECT fresh-event and shared host-clock-origin limitations are explicit in README.

Verdict: bounded PASS for this synthetic inert model only. Lead and independent
reviewer repeated both normal/-O runs at the frozen hashes. The reviewer also
checked 116 separate synthetic cases covering the exact prior counterexamples,
adjacent late ACKs in both clean terminals, quiet reset, recovery incident/boot/
proof/epoch binding, all five stale cleanup receipts, decimal-only grammar and
both rounding directions in all five phases. No false acceptance was found in
that finite checked set; this is not universal proof or implementation readiness.
Publication formatting removed only trailing empty EOF lines; Python ASTs are
identical to the independently reviewed revision. Both test modes were repeated.
No normal real launch: successful local costs remain UNKNOWN. No exploratory
SAFE_RETURN policy. No candidate admission, executable controller or live proposal.
