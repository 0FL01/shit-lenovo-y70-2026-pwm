# Timed factory-15 stock repetition 03

Status: completed on target; independent saved-hardware review PASS.
Source `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`; all 13 runtime blobs and
protocol match 01/02. [Immutable run](run.json) finished 2026-11-08
19:07:07 UTC. This was the third and last planned same-version repetition.

- P85 was `15 00 00` throughout; baseline/return C1 were `00 00 60` and
  middle C1 explicitly not measured. Only factory 15 was written. No error,
  reboot or unknown-value write occurred.
- Independent replay passed 28 strict envelopes, 81 rc-0 target events,
  20 clipped active calls, both protected-origin writers/tails and all five
  exact RX/native/profile captures. Headers were `1c 03 00 16`, request 3,
  scratch 16, raw/normalized count 9, with exact zero-miss native returns.
- Actual target quiet intervals were 2.124706–2.284462 seconds; PRE_GUARD
  durations were 0.21/0.16 seconds. Nine raw recording snapshots passed
  profile, continuity and skew checks. Holds advanced 149/149/165 sensor
  frames. The last count reflects a longer capture interval, not a shortened
  wait: the explicit return wait was 4.500108 seconds.
- Original native DBV 828, five Android settings, logger 0, ESD `reg_read`,
  root and Enforcing were verified. All child/writer/envelope cleanup, both
  watchdog disarms, owner release, camera stop and XML removal passed.
  Raw identities, owner bindings, logs and video remain private.

Measured host G was **31.614684608 seconds**, arm 1.146698690 seconds and
disarm 0.564788891 seconds. The total is near 02, but individual delays changed:
baseline C1 rose to 3.15749 seconds and sham quiet to 4.55006 seconds. Stable
whole-run time does not justify discarding those slower observations.

See the [three-run timing analysis](../p85_timed_stock_three_run_timing_20261108.md)
and separate [optical review](optical_result.md). Host 37 seconds does not
guarantee remote-child cancellation; the independent 60 second watchdog was
not renewed. These factory-only results do not admit 14 or establish a future
worst-case bound, physical PWM frequency, whole-waveform equivalence or comfort.
