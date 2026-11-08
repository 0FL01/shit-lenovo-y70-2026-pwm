# First timed factory-15 stock rehearsal

Status: completed on target; independent saved-hardware review PASS.
Source: `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`.
Finished: 2026-11-08 18:50:21 UTC. [Original run](run.json) is immutable.

## Scope and observed return

The explicit `p85-timed-stock-surrogate-v1` protocol used only factory page
23:85 value 15. Baseline and return C1 were `00 00 60`; P85 was `15 00 00`
in all three stages. Middle C1 is deliberately **not measured**, not inferred
from either adjacent control. Candidate 14 remained disabled.

Each hold retained the full 4.5 seconds after camera_start, with 149 advancing
sensor frames. Return prequiet ran within the middle optical wait, followed by
complete hold qualification and fresh protected-origin dispatch guards. Exact
factory return, P85/C1/native/DBV/ESD checks preceded confirmed short-watchdog
disarm; the final optical hold followed disarm.

Saved original native DBV 828, Android brightness 98/manual, min/peak 120.0,
timeout 1800000, logger 0 and ESD `reg_read` were restored. Camera stopped,
owned camera XML removed, both watchdogs disarmed and mutex released. The run
reported no error, recovery reboot or unknown-value write. Raw identities,
owner bindings, logs and media remain private.

Independent replay reconstructed all 28 strict envelopes and checked owner,
boot, state, protected-origin writer wire/tail and all five receive captures.
Each RX had DT `0x1C`, WC 3, valid ECC `0x16`, request 3, scratch allocation 16 and
raw/normalized count 9; exact profiles and native returns had no misses.
Actual target quiet intervals were 2.119–2.312 seconds. All 13 runtime source
blobs matched the recorded commit. Nine recording snapshots independently
passed the camera profile, continuity and skew checks. Raw final state,
scratch cleanup, both watchdog disarms and owner release also passed.

The reviewer's initial exact-string logger assertion was corrected to use the
actual `ctrl->ctrl->mipi_cmd_log_en: 0` format and the established parser; it
was not a device failure. P85/writer profiles were frozen before ESD resumed.
The unchanged shared C1 helper retains its older ordering, but both saved C1
captures had exact clean counters. Optical review is separate.

[Completed optical review](optical_result.md) independently reproduces the
limited fine/mean diagnostic result: main sham/baseline 1.0076336263 and
return/baseline 0.9940139036. Full-spectrum return L2 remains 11.98–12.86%,
so full/broad equivalence is unresolved. A second full decode exactly matches
the JSON and all 32 numeric profile arrays. No blanket or candidate approval
was created, and middle C1 remains explicitly unmeasured.

## Measured timing, not candidate admission

- Arm request to verification: 1.153986164 seconds.
- Full host arm-start to confirmed disarm G: **31.039259346 seconds**.
- Disarm: 0.569183115 seconds.
- Remaining to the host 37 second cutoff: 5.960740654 seconds.
- With a separate proposed J = 2 second variability margin and the existing
  8 second recovery reserve, this single G sample totals 41.039259346 seconds.

This is one observed stock sample, not a robust future bound. Retaining all
same-version phase maxima, including the slower baseline, gives 36.239293588
seconds before interphase residuals; with reserve and J that is 46.239293588
seconds and does not satisfy the 45 second criterion. See the separate
[timing analysis](../p85_timed_stock_latency_20261108.md). Negative provisional
partial-return estimates in the original report are preserved and explained
there; they were never a validated candidate admission gate.

The host cutoff cannot establish cancellation of an already-dispatched remote
child or a physical exposure bound. The independent 60 second watchdog was
not renewed. Uncertain evidence still requires verified same-target reboot,
not a blind write of 15. Ordinary reboot does not prove recovery from DDIC
damage. No physical PWM frequency, whole-waveform equivalence or comfort was
established by this stock rehearsal.
