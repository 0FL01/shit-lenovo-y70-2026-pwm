# Timed factory-15 stock repetition 02

Status: completed on target; independent saved-hardware review PASS.
Source `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`, identical 13 runtime blobs
and protocol to [01](../p85_timed_stock_a001_20261108_01/hardware_result.md).
[Immutable run](run.json) finished 2026-11-08 19:01:26 UTC.

- All three P85 reads returned `15 00 00`; baseline/return C1 were `00 00 60`.
  Middle C1 is explicitly not measured. Only factory 15 was written; no 14,
  error or reboot occurred.
- Independent replay passed all 28 strict envelopes, 81 ordinary target events
  with rc 0, 20 clipped active calls, both protected-origin writers and all five
  framed reads. Receive header `1c 03 00 16`, request 3, scratch 16 and raw/
  normalized count 9 passed with exact zero-miss profiles and native returns.
- Actual target quiet intervals were 2.153350–2.271919 seconds. PRE_GUARD took
  0.20/0.18 seconds, compared with 0.16/0.16 in 01. All nine raw recording
  snapshots passed profile, skew and continuity checks; holds advanced
  149/148/154 sensor frames without shortening the required 4.5 second wait.
- Original native DBV 828, five Android settings, logger 0, ESD `reg_read`,
  root and Enforcing were independently verified. Child/writer/envelope
  scratch cleanup, both watchdog disarms, owner release, camera stop and
  temporary camera XML removal passed. Raw identifiers, logs and video remain
  private.

Measured host G was **31.636799846 seconds**, 0.597540500 seconds longer than
01. Arm was 1.142998159 seconds and disarm 0.576029312 seconds. This sample
leaves 5.363200154 seconds to the host 37 second cutoff. It does not establish
a robust future bound, remote-child cancellation, or candidate admission.
Slower baseline phases remain in the conservative analysis.

[Optical results](optical_result.md) are reviewed separately. The factory-only
rehearsal establishes neither physical PWM Hz nor whole-waveform equivalence
or comfort. No candidate approval is created by this document.
