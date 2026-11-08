# Pure offline local sequence model

Status: **inert synthetic model only**. It cannot control a phone, execute a child,
read evidence files, open a socket, launch a shell/subprocess, or authenticate a
producer. There are no dependencies outside Python's standard library. No controller,
CLI command/transport adapter, hardware readiness or candidate admission is supplied.
Unknown P85=14 has no positive state, enum, plan or dispatch path.

Normative design: `artifacts/p85_local_sequencer_integration_design_20261108.md`,
Git blob `baf374e23fc2e7b57f7b3ca2a6d660dfe8c618e4`. The four corrected contracts
and final review clarification are mandatory. Runtime `1785d32` is not changed.
Only this new directory is written. No private corpus is consumed.

## Run and scope

From this directory:
- `PYTHONDONTWRITEBYTECODE=1 python3 -B run_tests.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -O -B run_tests.py`

The scripts run synthetic transitions and unittest checks, not external commands.
No bare assert is used. Frozen dataclasses reject unknown constructor fields.
Events validate payload classes exactly; numeric fixtures reject bool, negative,
NaN, infinity and unreasonable magnitude. Finite enums supply all operation kinds.
Public Model is a one-shot in-memory cursor with step(Event), a read-only snapshot,
and a shared synthetic Ledger. It never adopts a supplied execution snapshot. After
arm/reservation, malformed or out-of-order target events latch uncertainty before
raising; catching the exception and submitting a replacement cannot resume a child.
Malformed/replayed camera ACKs instead retain sticky optics failure, requiring an
explicit qualified degraded-return branch before any further child. Public-cursor
regressions test all five phases at four consumed-invocation checkpoints.
Private frozen _Snapshot/_LedgerSnapshot objects are reducer fixtures, not public
execution APIs or a security boundary against deliberate Python introspection.
Tests explicitly branch these independent synthetic worlds with replace. There is
no serialization parser. Do not build a public controller around the private reducer.

Exactly five children: SHAM15_WRITE, SHAM_P85, RETURN15_WRITE, RETURN_P85,
RETURN_C1. Baseline is an epoch-bound prerequisite fixture, not a sixth invocation.
The middle C1 is **not_measured**. Factory P85 is exactly [21,0,0], return C1
exactly [0,0,96]. The writer's abstract payload is [21]; it is not a DSI command
or a claim to reproduce unchanged writer bytes.

## State/event contracts

Every child is reserved/consumed before DISPATCH, then has one actual producer
result, one sealed receipt, and matching fixture E/C/S/I/W verdicts. A receipt binds
epoch, boot, phase, reserved nonce, manifest/source/plan, original protected origin,
the exact three synthetic published artifact identities, seal identity, payload,
producer result and gates. Even a valid receipt from another phase cannot substitute.
Producer UNKNOWN, nonzero rc or stderr fails sticky; neither SUCCESS text nor a
replacement receipt can repair it. Required gate bundles are E/C/S/W for writers,
E/C/S/I for reads. Guard fixtures include native/state/owner/boot/ESD, retained
origin and collision checks; exact GUARD_TIMING grammar requires 0 <= delta <= 8
under BOTH exact bounded Decimal arithmetic and the inherited Python float predicate.
This conservative intersection rejects float-rounding false acceptance without
expanding the inherited caller's acceptance at the opposite rounding boundary.
Both timing operands require integer digits, a decimal point and fractional digits,
plus the exact final LF; integer-only and mixed integer/decimal forms are rejected.
Fixture quiet requires at least two seconds. These are fixture outcomes, not
implemented acquisition/decoding/validation. Freshness tokens are invocation-bound
once-only model IDs, not evidence of real snapshots.

NORMAL_RESERVED requires all four disjoint successful-cost terms Known:
current + downstream + jitter + uncovered, strictly before immutable expiry.
Qualification IDs must explicitly begin SYNTHETIC:. They do not qualify any real
local cost. UNKNOWN blocks the initial normal grant, every reservation and
SAFE_RETURN. A known successful-operation cutoff crossing selects uncertainty,
not cancellation or a return promise. Timeout bounds of 30–38 seconds do not fit
the normal suffix, as tested; measured host decoder maxima are not input qualifications.

EXPLORATORY_FACTORY15 accepts UNKNOWN *costs* while retaining all target gates and
37/45/8 constraints; it promises no reserved suffix. Its clean terminal is only
EXPLORATORY_STOCK_SAMPLE. It has **no SAFE_RETURN edge** because no separately
reviewed exploratory degraded policy exists. Policy is fixed for the epoch and
cannot be changed by any event. Normal SAFE_RETURN needs qualified costs, completed
return prequiet and fresh original-HOLD_BEGIN guard. It permanently sets degraded
classification and optics_invalid. It can never yield RUN_COMPLETE.

Host/device clocks are separate fixtures. One grant uses
floor(anchor + 37 - host_elapsed - margin), with anchor <= current device time,
an explicitly PASS *synthetic clock-contract assumption*, and no renewal. Host37
is independent of device expiry. 45 total policy leaves 8 recovery reserve, **not a
promise that reboot finishes within 8 seconds**. SHORT60 is immutable from arm;
OVERALL600 is independently inherited in this model at host time zero. Watchdog
expiry is uncertainty; no native cancellation is modeled. A suspension/rate guarantee
or real monotonic clock implementation is NOT provided by the clock-contract fixture.

Start/end ACKs bind epoch/boot/camera/manifest/stage/nonce/sequence/session/full
requested and observed profile/metadata reference, settlement and continuity.
End references the accepted start and requires >=120 progressing sensor frames and
advancing timestamps. The minimum 4.5-second local hold starts at *receipt* of a valid
start ACK, never backdated to its sensor timestamp. Accepted ACKs are once-only.
An invalid ACK sets optics_invalid; a later valid replacement is refused.
Sensor frame continuity is a fixture assertion, not proven from two endpoints.
A local timer or ACK cannot establish encoded60, actual PTS or an FFT verdict.
CAMERA_START clears any pre-start quiet fixture: normal completion needs a fresh
in-hold quiet after the accepted start ACK. Pre-start quiet can only satisfy the
separate explicitly degraded SAFE_RETURN branch. Late malformed/replayed camera
events after either clean terminal invalidate that terminal to DEGRADED_COMPLETE,
retaining optics failure without inventing target uncertainty or new cleanup work.

## Return, recovery, cleanup and spent epochs

RETURN_PROOF denotes the complete local exact return fixture, still before SHORT60
disarm. LOCAL_RETURNED is LOCAL_STOCK_RETURN_VERIFIED plus verified short disarm.
It leaves OVERALL600 and all separate cleanup obligations live. It is not full-run
success. Final capture/camera stop and hardware audit precede guarded restore;
offline PTS/FFT/optical review is possible only after all cleanup, including owner
release last. Modified settings/watchdogs/lock cannot be kept waiting for FFT.

Any hardware/source/receipt audit contradiction, including one arriving after local
proof or a clean terminal, sets target_uncertain permanently and requires same-target
verified changed-boot recovery before target restore. Recovery permits restoration;
it never resets sequence execution or the sticky uncertainty/degraded class.
Each target failure advances a model incident and revokes earlier recovery. Recovery
binds epoch, current incident, target, old/current boot, never-before-seen new boot
and a once-consumed proof identity. Acceptance advances current boot; original child
receipts stay immutable historical facts with their original boot. Every cleanup
receipt additionally binds the current boot and incident, and is consumed once for
its pending obligation. Old restore/disarm/owner/camera/scratch receipts cannot close
new obligations after another audit rejection, even after a fresh verified recovery.
Each cleanup item requires its own epoch-bound verification; UNKNOWN/FAIL does
nothing. Camera stop/collection remains pending on host disconnect. A reconnected
host must supply a synthetic camera-reidentification prerequisite before camera
cleanup/ACK use. The model invents no cross-phone control.
RECONNECT is explicitly a fresh-event fixture assumption, not a consumed/authenticated
camera receipt: no connection-generation protocol is implemented. Each use assumes
new external reidentification. Its reusable synthetic label is not proof of freshness.

Crashes and restarts never resume a child and never clear the spent ledger.
Even after scratch cleanup and owner release, a spent epoch cannot stage again.
Missing/ambiguous authoritative ledger refuses launch. A shared synthetic Ledger
keeps immutable spent snapshots across separate public cursors, including cursors
created before consumption. It only models persistence; durable storage,
interprocess atomic consumption/sealing, root-backed records
and crash-safe reconciliation remain **unimplemented**. No files are used as a ledger.

## Tests and limitations

The named transition matrix covers every State x EventKind pair using canonical
fixtures with an explicit allowed/refused oracle, plus sticky/expiry/nonce/terminal
invariants. Dedicated tables cover all five child phases and checkpoints before
reserve, after reserve, dispatch, result and seal; crash/restart/timeout/audit fault;
swapped bindings, unknown/nonzero completion, gate FAIL/UNKNOWN, source/origin/plan,
factory payload, strict timing and guard grammar, ACK bindings/hold/continuity,
unknown/slow costs, watchdogs, audit-after-proof, recovery, partial cleanup and
relaunch after cleanup. Counts and exact source blobs are frozen in RESULTS.md.
The matrix is exhaustive over its finite canonical cases, **not universal proof**
over all numeric values or arbitrary event histories. It is neither fuzzing nor
model checking of an actual implementation.

Still unproved/unimplemented:
- Root versus UID2000 launch/sealing, shared-UID races, actual producer rc/stderr,
  protected-origin acquisition, complete owner predicate and source staging.
- Real E/C/S/I/W invocation and full retained native/tail/ESD evidence.
  The state-without-ESD adapter mismatch is not patched by a fake PASS.
- Durable spent ledger, kill/power-loss publication and recovery reconciliation.
- Actual sensor metadata/encoded60/PTS/FFT and physical optical measurements.
- Android capabilities, clock/suspend/rate assumptions, max-cap ingestion/storage/
  decoding/validation costs and the entire successful return suffix.
- Separate setup-time and active-start host clock origins: this conservative model
  uses a common zero for host37 and inherited OVERALL600. Slow baseline beyond37
  refuses a grant rather than representing the real separate post-setup start37.

No physical test is proposed or authorized by this deliverable. No PWM frequency,
DDIC safety, Android timing, controller readiness or candidate14 approval follows.
