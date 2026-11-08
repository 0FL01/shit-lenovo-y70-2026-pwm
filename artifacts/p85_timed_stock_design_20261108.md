# Timed factory 15 surrogate: exploratory stock-only protocol

Status: isolated offline implementation, awaiting independent review and a new
committed-source stock rehearsal. No device operations, commit or push by the
implementer. Candidate 14 is hard-disabled. Factory 15 writes are already observed
on this panel, but are not claimed risk-free. No result establishes PWM Hz.

New files:
- `06-tools/run_p85_timed_stock_trial.py`
- `06-tools/test_run_p85_timed_stock_trial.py`

All existing qualified executable sources and child programs remain unchanged.
The source gate binds the original 12 executable files plus the new runner.
The separately maintained timed optical analyzer is not a runtime dependency.

## Explicit protocol change

Report scope is `p85-timed-stock-surrogate-v1`, with `candidate_enabled: false`
and `timed_stock_exploratory: true`. Stages remain baseline, sham15, return15.
Baseline requires P85 = [21, 0, 0] and C1 = [0, 0, 96]. The timed sham requires
P85 = [21, 0, 0], every native/state/owner/boot/ESD guard, and the full optical hold.
Its purely diagnostic C1 read is explicitly NOT MEASURED:

    {"status": "not_measured", "reason": "diagnostic omitted by timed-stock protocol"}

There is no C1 data or C1 phase duration in that stage. Return still requires the
full P85 = 15 and C1 = 60 read plane, native 120/group 3, DBV 3600, ownership, boot,
ESD and exact writer evidence before short-watchdog disarm. This is a scientific
protocol change, not fabricated equivalence with the old complete-C1 run.

## Exploratory admission, not candidate permission

The coordinator approved an explicit bootstrap distinction: factory-only stock
rehearsal may measure unknown arm/disarm/full-path timings without pretending a
proven whole-return bound already exists. Each action records remaining time and
a provisional partial return estimate, including an explicit list of unknown
components. The estimate is NOT a safety bound or candidate admission gate.

The host clock starts before arm construction/request. A main-thread SIGALRM and
transport proxy enforce a 37 s host cutoff, retaining the 8 s recovery reserve
within the unchanged 45 s active policy. An existing realtime alarm is refused.
All panel/camera/envelope shell calls are clipped to remaining host time; late
results are rejected. The alarm is canceled and the prior handler restored before
recovery or cleanup. An uncertain arm is latched before dispatch. Lost disarm
response is a failure, not a successful completion.

The independent device watchdog remains the SAME fixed 60 s program with no
renewal path. Its arm is verified before the first writer. It is disarmed only
after verified full return or verified changed-boot recovery. There is no 14 CLI,
constructor mode, writer stage or arm path in this runner.

The existing remote child and envelope timeout semantics remain unchanged.
The 37 s cutoff is a HOST decision/transport-return deadline, not proof of remote
cancellation. A previously dispatched child can outlive it. No subsequent DSI or
blind return 15 is allowed after timeout or uncertain evidence; same-target reboot
and the independent watchdog are the recovery path. Reboot does not prove physical
DDIC recovery. Kernel hardware actions are not made atomic by process termination.

## Scheduling and protected dispatch

1. Complete normal setup, one continuous camera recording and full baseline.
   Original native brightness is captured, never assumed to be 828 or 6438.
2. Fresh target/camera identity, camera metadata and state checks precede complete
   first-writer pre-state / 2 s quiet / post-state qualification and collision check.
3. Start the host clock, arm and verify the immutable watchdog. Immediately before
   the prepared factory 15 writer, obtain a fresh host-validated native/state/owner
   snapshot covering the protected quiet origin through a new dispatch marker.
4. The new readonly PRE_GUARD section runs on-device immediately before the exact
   unchanged child. It checks root ownership, boot, DBV, DC, power, Enforcing and
   panel name. Checked file-backed dmesg is bounded to 16 MiB. Its unique protected
   origin must retain the correct native tuple before it; any subsequent mode,
   DSI transfer, failure or LOST evidence fails, including a transient mode change
   that returns to 120. Writer nonce collision is checked across the whole log.
   The unchanged child also retains its own panel/module/native transaction gates.
5. Host validates the ordinary writer interval AND the full protected-origin
   interval. Native events after END but before dump are additionally rejected.
   This detects the remaining guard-to-callback race; it is not an atomic lock.
6. Sham observation retains its complete prequiet and P85 read with all validators.
   After hold begin and camera_start, run the entire return pre-state / 2 s quiet /
   post-state sequence. Wait the remainder of 4.5 s after camera_start completes.
   If prequiet overruns, extend the hold, never shorten it. Then camera_end and
   complete hold/native/state/progress qualification must succeed.
7. Use the final hold origin/snapshot for return collision and fresh dispatch-gap
   checks. The return writer cannot start before the completed sham hold. Apply
   the same remote guard and post-child protected-origin validation.
8. Full return observation quiet, P85 and C1 qualification precedes disarm. The
   final return optical hold runs after confirmed disarm and host alarm removal.
   Camera stop, original settings/DBV/logger/ESD restoration and owned cleanup
   remain mandatory before successful software completion.

Every hold retains at least 4.5 s after camera_start and 120 advancing sensor
frames. Central 60 encoded-frame qualification remains the offline analyzer's
job. Camera/target operations are not parallelized. Read-only prequiet activity
inside the sham hold is a changed acquisition condition requiring optical review.

## Evidence, timing and cleanup

`return_prequiet` records host start/end, wait, overlap and overshoot. With
`deadline = camera_start.host_capture_bounds.end_monotonic + 4.5`:

    wait = max(0, deadline - prequiet_end)
    overlap = max(0, min(prequiet_end, deadline) - max(prequiet_start, camera_start_end))
    overshoot = max(0, prequiet_end - deadline)

Quiet evidence includes actual target kernel marker timestamps with delta >= 2 s.
These timestamps are not mixed with host or camera clocks. Camera snapshots keep
truthful UTC/host monotonic call bounds. Sham records `hold_verified_monotonic`;
writers record start, dispatch and validation bounds. Quiet age to callback is a
conservative host upper bound through validated child completion, not a calibrated
kernel/host clock conversion. PRE_GUARD reports its own device-uptime duration.
Camera_end-to-dispatch gap includes the fresh dispatch checks. Nested intervals
must not be added twice.

The report includes `arm_seconds`, `arm_request_to_verified_seconds`,
`return_qualified_monotonic`, `disarmed_monotonic`, `disarm_seconds` and actual
`active_G_seconds`. G and D use the same captured completion timestamp. Every
transport action records the remaining active budget and explicitly provisional
partial return margin; envelope/validation/save phase timings remain available.
Report fields declare watchdog 60 s and renewals 0.

The only extra device scratch file is exact `guard-kernel` inside the existing
fresh per-envelope owned directory. Normal and remnant cleanup remove only that
known basename plus the previous fixed files. Remnant owner/UID/mode/symlink
checks remain mandatory. Missing owner sentinel or unrelated files are not guessed
away. No broad deletion, dmesg clearing, payload truncation or log-sized argv.
All raw evidence and video remain private. Public reports carry no identities.

## Future decision and execution

Actual measured G is distinct from conservative phase projections. Slow/cold
samples must be preserved. Multiple successful same-version factory rehearsals
and optical review are required before even considering a separate candidate
implementation. The unchanged criterion remains:

    G_bound + J + 8 < 45

J must be positive and evidence-supported, not selected only to force a pass.
A first successful G near 37 s does not admit a candidate. Failure to fit the
cutoff is a measured blocker, not permission to remove safeguards or extend it.

After review and a clean relevant-source commit, the coordinator alone may run:

    python3 06-tools/run_p85_timed_stock_trial.py "$TARGET" "$CAMERA" --stock-only \
      --experiment-id p85_timed_stock_unique --output artifacts/p85_timed_stock_unique

Default is no-I/O preflight with no output/private directory creation. Only the
coordinator adds `--execute` after fresh private transport identification. The
private cache is `~/.cache/legion-y70-p85-timed-stock/<experiment_id>/`.
Maximum-input command-size checks run before any live I/O and check every final
service/argv against the existing 65,535 / conservative 131,072 byte ceilings.

## Frozen offline verification

- Full suite: 240 tests passed, 2 skipped.
- Focused timed/batched/metadata/transaction group: 117 tests passed under `-O`.
- Independent reviewer: all 15 new timed tests passed both normally and under
  `-O`; real generated-shell scratch cleanup and exact owned remnant cleanup
  additionally checked. No consequential code blocker remains for separately
  coordinated exploratory stock-only qualification after clean source commit.
- Frozen runner blob: `9c804b7f12c5a77768d2487c31703b66c540f62c`.
- Frozen test blob: `8185ffa41251ae961b094677a139eda84c528930`.
- Maximum final service size: 30,156 bytes. Offline preflight creates no output or
  private directory. The uncommitted new runtime source correctly blocks execute.
- All 12 previous runtime source blobs remain unchanged. No hardware qualification
  of this new timed protocol has occurred.

Before any future unknown-value admission, the physical active-window bound and
remote continuation after host timeout require their own reviewed treatment.
This factory-only rehearsal does not settle either issue or enable candidate 14.
