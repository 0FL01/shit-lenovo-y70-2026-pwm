# First isolated batched P85 stock qualification

Status: completed on target; independent saved-hardware replay PASS.
Optical review is recorded separately.
Source commit: `881ffb7e501d95205ad3f9ac8ece89adb143387e`.
Finished: 2026-11-08 18:18:28 UTC. The immutable [run](run.json) retains
`awaiting_optical_review`; this document records subsequent review separately.

## Completed scope

- Baseline → factory sham 15 → factory return 15, at native DBV 3600 and
  actual 120 Hz / group 3. Two bounded runtime writes used factory page 23:85
  value 15, with the unchanged qualified child programs. No 14, C1 write,
  initialization replay, persistence, flash or security-setting change.
- All three P85 reads returned `15 00 00`; all three C1 reads returned
  `00 00 60`. The framing/native/wire and whole-stage checks accepted each
  phase before proceeding. Same-value writes do not establish read/write-plane
  identity, frequency semantics, volatility or a safe unknown value.
- The original state captured for this run was native DBV **828**, Android
  brightness 98/manual, min/peak refresh 120.0, timeout 1800000 and logger 0.
  Those values were restored and verified. Camera stopped, temporary camera
  XML removed, ESD `reg_read` restored, watchdog disarmed and mutex released.
  No error or recovery reboot was reported. The previous run's original 6438
  was not substituted for this run's actual snapshot.
- All raw envelopes, device identifiers, owner bindings, video and screenshots
  remain private. Public evidence contains source identities, measurements and
  verification flags only.

## Independent saved-hardware checks

All 26 envelopes were reconstructed from their private owner-bound manifest
and passed exact framing, UTF-8, section order, status, completion, boot and
state checks. Both writers passed the unchanged native-return and exact-wire
validators: standalone callbacks 11/9/11, pending 0, flags 0. All six long
three-byte reads had header `1c030016`, count 9 and exact zero-miss profiles.
Quiet and hold intervals showed no DSI write or mode transition.

All 12 executable blobs matched the recorded commit. All 75 ordinary target
events returned zero without stderr; eight camera snapshots retained the same
session/settings and the three holds advanced 149/163/149 sensor frames.
Independent replay verified the original native 828, five Android settings,
logger 0, ESD `reg_read`, camera stop, all 26 envelope removals, eight child
cleanups and watchdog/mutex release. No reboot or unknown-value write occurred.

## Timing result

Observed complete stage times were 18.548829, 16.668455 and 15.953030 seconds.
Factory write phases, including their pre-quiet gates, took 6.673705 and
6.589434 seconds. This is substantially shorter than the prior unbatched
31–33 second stages and roughly 17 second writer phases.

It still does **not** admit the proposed unknown-value experiment. The same-run
phase-max active surrogate is 43.647907 seconds; adding the unchanged 8 second
recovery reserve already gives 51.647907 seconds, before short-watchdog arm,
disarm and a positive variability margin. The candidate remains disabled.
No safeguard was relaxed to turn this result into a timing pass.

The next step is saved optical/raw validation and a separately reviewed
scheduling design, followed by another stock-only qualification if needed.
This result proves neither physical PWM frequency nor the required >=2000 Hz.
