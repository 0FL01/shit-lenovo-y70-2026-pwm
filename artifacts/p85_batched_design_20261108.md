# P85 batching: isolated stock-only qualification adapter

Status: offline implementation and tests only. No ADB/device actions, commit or
push in this work. Candidate is explicitly disabled in this adapter, including
constructor, CLI, arm and write builders. No timing admission has been relaxed.
The unchanged 45 s active / 60 s independent watchdog limits are not evidence that a
candidate can fit them. New same-version stock measurement and optical review
are required before a separately reviewed admission design.

## Files and retained qualification

New executable files:
- `06-tools/p85_batched_envelope.py`
- `06-tools/run_p85_batched_trial.py`

New tests:
- `06-tools/test_p85_batched_envelope.py`
- `06-tools/test_run_p85_batched_trial.py`

The qualified child builders, C1 helpers and existing runner remain byte-for-byte
unchanged from source 86ffbfd76aed81b95ca0e990362dd55aacca99a8. Each child command is
compared byte-for-byte in tests and executed as its own foreground subprocess,
with the same root context and internal timeout/traps/native gates. Exactly one
DSI child exists per read/write envelope. No joined write → read → return program.
The original independent readonly ESD mount-namespace script is retained.

The completed stock-only 04 qualified baseline/sham/return at native 3600 / actual 120
and two factory 15 runtime writes. It restored the actual saved original native 6438,
not 828. New setup regression starts from 6438 and preserves that snapshot through
one guarded native 3600 dispatch. Every run still restores its own captured value.
04 does not physically qualify this new batching code.

## Boundary reductions without removing predicates

- State: one envelope contains fields, display, boot and root owner checks.
  Display/boot retain normal shell UID; root fields/owner retain `su -c`.
- Quiet: separately host-validated pre-state, then begin → sleep 2 s → end → dmesg → post-state
  envelope. All quiet/native/post-state checks finish before another child.
  Initial batching qualification deliberately does not retry a rejected quiet.
- Read/write: begin → unchanged one child → end → dmesg → state → readonly ESD. Existing
  framing/native/wire/pending/flags/profile/ESD/state validators all run on host
  before another child. Stock P85/C1 expected values are checked before proceeding
  to the next child, not merely at the end of the stage.
- Write pre-quiet is retained; writer marker collision is checked against that
  freshly validated quiet snapshot before dispatch.
- Optical hold remains begin marker → camera_start → sleep 4.5 s → camera_end → target end.
  Only the post-camera end/dmesg/state reads are batched. At least 120 advancing
  sensor frames and independent central 60 encoded-frame review are unchanged.
  No camera/target parallelism and no PTS = sensor timestamp assumption.

These sequential snapshots are NOT atomic and do not lock compositor/native
writers. No log truncation, activity whitelist, dmesg clear or register changes
were introduced. No 14, C1 writes, latch/reset/sleep/init replay or persistence.

## Framing, status and lifecycle

The outer script runs as shell UID 2000 with a fresh 0700 workdir. Root components
use the original `su -c` context. Fixed bounded sections have nonce-specific
start/header/end/completion markers and explicit stdout/stderr byte counts plus
actual component exit status. Payload is streamed from owned files, never passed
as a large argv. Host rejects missing/duplicate/reordered/embedded delimiters,
truncation, nonzero status, any stderr, oversized payload, invalid UTF-8, NUL and
trailing output. Limits include 16 MiB dmesg, 4 MiB display, 1 MiB child and 24 MiB total;
oversize causes failure rather than truncation. Every subcommand runs with `set -e`
except the unchanged already-bounded child, whose exact status is captured.

Child internal timeout remains unchanged; an outer foreground timeout bounds the
individual component and envelope using already-used system mechanisms. No
background DSI task or next child is scheduled by the envelope. Host disconnect
or hard kill does NOT prove cancellation: the already-authorized single child
may still run, even if the connection was lost before its start. Its own timeout
and device watchdog remain the fallback. Kernel/DDIC execution is not made atomic
or necessarily interrupted by process termination. The host retains uncertainty
and cannot start a new child/15 until existing verified same-target recovery.
Tests demonstrate bounded surrogate child behavior, not an Android cancellation
or hardware recovery guarantee. Independent device watchdog remains essential.

Normal cleanup removes only stdout/stderr/owner and the owned directory. Remnant
cleanup verifies UID 2000, 0700 directory, 0600 nonsymlink owner sentinel and exact
nonce + digest bound to this run's root owner verification command. No wildcard,
foreign-directory adoption or broad deletion. An atomic private envelope manifest
is saved before dispatch so exact paths/bindings survive host failure. A missing
sentinel (e.g. hard kill between mkdir and sentinel creation), or an unexpected
extra file, fails cleanup and preserves recovery state; no ownership is guessed.
Root mutex checks and inherited watchdog/settings/logger/ESD/camera cleanup remain.

## Timing and admission

The report retains `stages[].phase_seconds` for quiet/P85/C1/hold+metadata and
`writes[].elapsed_seconds` including pre-quiet. New `envelope_timings` records
monotonic call bounds and `phase_timings` records framing validation, host
validation, qualified read and host saves. Host call durations include command
construction, transport and device work: they are NOT pure RTT. Completed final
save duration is included in stage/write elapsed time and persisted by the next
normal report save. Raw envelopes and image/video remain private.

Source binding includes the original 10 executable paths plus the two new ones.
The live CLI refuses dirty/untracked relevant sources before directory creation
or device I/O. Docs-only commits remain compatible through unchanged Git blobs.
The new report identifies `p85-batched-stock-v1` and `candidate_enabled:false`.

The measured 04 plan remains in `artifacts/p85_latency_plan_20261108.md`. Required
future model is A + 2W + O_candidate + V_return + D + J + 8 < 45 with positive measured variability
margin, successful same-version stock maxima plus fresh baseline/sham, and a
remaining whole-return-path check. A/D/J and batched performance remain unknown.
No successful run of old/unbatched code substitutes for these measurements.

## Proposed coordinator command after independent review and commit

Freshly bind TARGET/CAMERA using private transport procedure; never assume old IDs.
Default is offline and creates no output directory:

    python3 06-tools/run_p85_batched_trial.py "$TARGET" "$CAMERA" --stock-only \
      --experiment-id p85_batch_stock_unique --output artifacts/p85_batch_stock_unique

Only the coordinator adds `--execute` after reviewed-source commit and preflight.
Private artifacts use `~/.cache/legion-y70-p85-batched/<experiment_id>/`.
A successful run still ends `awaiting_optical_review`, not a PWM/physical-recovery
claim. Candidate CLI does not exist.

## Offline validation checkpoint

20 new tests PASS within the full suite: 203 tests PASS, 2 skips.
All 95 P85-named tests also PASS under `-O` (including new batching tests).
Coverage includes every component failure, exact unchanged child commands,
large retained logs, strict malformed framing/UTF8/status cases, ownership and
cleanup refusal, host timeout/HUP/TERM/hard-kill before/during/after a bounded
surrogate child, every P85/C1/writer failure boundary using real existing host
validators, hold-end/state/ESD failures, prevention of next child/15 before reboot,
actual-original 6438 setup, private manifest and monotonic timings. These are
mock/offline regressions, not live or hardware qualification.


The no-I/O CLI also builds envelopes at maximum permitted token 128, marker 180
and experiment-ID 64 lengths. Final UTF-8 `shell,v2,raw:` service sizes are P85
29339 bytes, C1 29332, and either writer 27316, below the actual GuardedADB 65535
service limit. Each script construction checks that final service size before
transport. The complete quoted outer command plus NUL is also checked against
the conservative 131072-byte Linux/Android argument ceiling; nested literal
commands are shorter. Multi-byte oversize rejection is tested. The size report
is saved as `envelope_command_size_preflight`. No original child is changed.
