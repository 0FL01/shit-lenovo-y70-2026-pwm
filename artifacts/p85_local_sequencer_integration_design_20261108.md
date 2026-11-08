# Minimal local stock sequencer: integration design, not implementation

Status: OFFLINE proposal only. No device action, executable controller, admission,
or physical PWM claim. Unknown14 MUST remain structurally unsupported. Reviewed
checkout at inspection: `97b4682957e90f088760fccdeaa50d33ecbf2b02`; qualified runtime
remains `1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2`. Envelope spike was still
unreviewed at inspection. Finite-corpus semantic success is not live readiness.

## Scope and invariant

One foreground finite supervisor, one unchanged child at a time, one experiment
per process. Retain existing host setup/baseline/camera/restore machinery; replace
only the active target sequencing after independent review. No service, autostart,
credential, binary install, UI, replay/resume command or watchdog renewal.
Local semantic checks replace the corresponding host decision BEFORE the next
child; host independently audits the complete evidence afterward. Host loss alone
is not local child uncertainty; loss of authoritative local evidence always is.
A host with uncertain output never dispatches a replacement writer.

Two different terminal claims:
- LOCAL_STOCK_RETURN_VERIFIED: exact return15 callbacks/wire, P85=[21,0,0],
  C1=[0,0,96], native120/group3, DBV3600, boot/owner/state/ESD and tails verified,
  followed by confirmed SHORT60 watchdog disarm. Inherited OVERALL600 remains
  armed until the existing restore/recovery contract completes. Not optical or
  full-run success.
- RUN_COMPLETE: additionally host audit, mandatory final return optical hold,
  camera stopped/collected, actual metadata/PTS/encoded60 qualification, all original
  settings/DBV/logger/ESD restored, owned remnants cleaned and mutex released.
Neither proves physical DDIC recovery or >=2000Hz.

## Fixed inputs, staging and acquisition contract

A trusted host manifest pins: reviewed controller/validator sources and Git blobs;
unchanged generated child bytes and their digest; allowed stage sequence; nonce
per child/envelope; expected section plans/caps/root/timeout; experiment epoch;
expected target boot/model/panel/module; native reference; owner token binding;
original settings/DBV/logger/ESD recovery record; and distinct camera identity.
Digest checking here identifies executable inputs, not routine log hashing.
No kind, command, path, bound or expected marker is derived from received evidence.
No candidate14 parser option, manifest value or stage exists. P85 reader accepts
only factory data in this coordinator; generic decoder success is insufficient.

One-shot bootstrap must refuse existing paths, symlinks/hardlinks, wrong owners,
permissions, source mismatch or nonce collision. Freeze code/manifest independently
of mutable evidence; separate root-owned control/recovery record from shell-UID2000
workspace because existing envelope commands require UID2000 and exact root su
boundaries. Preserve those contexts, do not run every old envelope as root.
Define one writer per evidence file; capture real producer rc/stderr, then seal the
file before decoding. Status is published only after all gates, never a bare ACCEPT
line supplied by a child. Staging immutability against shared-UID writers is NOT
established by stat/chmod alone. Exact root/shell launch, sealed handoff and ownership
protocol need an offline design/test before integration; no adversarial same-UID
security claim. No persistent access is introduced.

All acquisitions are fresh executions in the expected epoch/boot/phase. Each output
is associated with the reserved invocation before dispatch, not by parsing its
self-reported nonce. Log retention must contain original protected origin, latest
native anchor, unique markers and full tail. Missing history is refusal, not retry.
Producer success, cap, stderr and envelope completion are checked independently;
non-atomic snapshots remain non-atomic. Fresh local owner check must execute the
existing complete ownership predicate; empty OWNER output alone proves nothing.

## Gate bundles and exact component boundaries

E: `offline_local_envelope_spike/decode.sh RAW PLAN NONCE RC STDERR OUTPUT`,
requiring successful invocation and exact SUCCESS marker; trust expected plan and
actual producer rc externally. This is byte framing only (ASCII stricter subset).
Do not use partial .stage output. Budget od expansion/storage and every producer.
C: `offline_local_validator_spike/validate_capture.sh OUT ERR NONCE KIND RC`,
then exact coordinator stage payload policy. This verifies completed child capture,
not source/freshness. Exact KIND values are `write` for both stock writers,
`85` for P85 and `C1` for C1. Bind kind from manifest, never output.
S: `state.awk` over independently acquired FIELDS/DISPLAY/BOOT/OWNER/ESD, expected
boot from manifest, with E/producer/ownership checks around it. Current quiet/state
plans have no ESD section: do NOT fabricate one to satisfy this fragment. Integration
must supply a separately acquired real ESD snapshot or a reviewed state-only adapter
matching existing validate_state; this interface mismatch remains open.
I: `offline_local_interval_spike/validate.sh MODE BEGIN END ACTUAL NONCE LOG OFFLINE`
for quiet/read/dispatch/guard; these remain offline interfaces, not execution grants.
W: writer_wire.awk after bounded immutable kernel ingestion, with original protected
origin plus child BEGIN/END; combine with C, S, producer and ownership gates.

For every child: E + C + S + I(read) or W(writer), independent ESD=reg_read,
post-END-to-dump rejection of DSI/mode/failure/LOST, matching boot and phase. Checks
run before any next child. Preserve full source/module/owner gates INSIDE unchanged
child. Never substitute debugfs TX bytecount for native return evidence.
For writer dispatch: fresh state and dispatch interval from ORIGINAL protected
origin, full retained-log writer nonce collision check, then unchanged PRE_GUARD
immediately before child. Validate its real complete result exactly as current
caller: `GUARD_TIMING decimal decimal` plus LF, 0<=end-start<=8. Port parsing and
failure propagation; do not fabricate timing or equate uptime with host/kernel
clocks. PRE_GUARD failure prevents child; post-child guard/tail failure latches
uncertainty. Return protected origin is SHAM15_HOLD_BEGIN, never the later quiet.
I(read) does not whitelist exact read packets; unchanged child capture/native gates
and existing read-interval policy remain mandatory. Do not claim new wire coverage.

## State/transition table

Every child-dispatch row requires epoch/boot/owner continuity, target_uncertain=false,
complete evidence and the selected admission policy below. optics_invalid forbids
normal success, not an independently qualified degraded return; cleanup_pending
forbids run completion, not verified recovery. Recovery states may be entered with
sticky latches set. Current normal admission is BLOCKED by UNKNOWN_BOUND. A child is
reserved once before launch; no retry edge exists. Target and camera commands are
not newly parallelized. NORMAL follows rows top to bottom.

| State | Evidence producer and required transition | Failure / host loss |
|---|---|---|
| STAGED | Source/staging verifier proves manifest, unchanged child bytes, capabilities, no previous epoch. | Abort before arm; only proven-owned cleanup. |
| BASELINE_READY | Existing host setup + baseline quiet/P85/C1/optics; both identities; original recovery record; first-writer prequiet and fresh camera metadata. | Abort; existing guarded restore, or reboot if target uncertain. |
| CLOCK_GRANTED | Host starts37 clock BEFORE target anchor request; one-shot local absolute expiry grant established below. | No writer; arm uncertainty requires recovery. |
| ARMED | Exact immutable60 watchdog arm and existing owner/PID/armed verification complete. | Latch target uncertainty; no DSI; reboot policy. |
| SHAM_DISPATCH | Fresh state, original prequiet-origin dispatch interval/collision, local PRE_GUARD. | Latch; no child. |
| SHAM_CHILD | Unchanged sham15 writer; E/C/S/W/tail/ESD all pass. | Any unknown result => latch and reboot-only. |
| SHAM_QUIET | Fresh prestate, BEGIN/sleep2/END/full dump/poststate; I quiet and actual>=2s, S policy. | Latch; no read. |
| SHAM_P85 | Unchanged long3 reader; E/C/S/I/read-tail/ESD; exact [21,0,0]. Middle C1 explicitly not_measured. | Latch; no further DSI. |
| HOLD_START | Target HOLD_BEGIN then host camera_start metadata, request/results settled and epoch/stage-bound ACK. | Missing ACK => optics failed; safe-return branch only if local evidence intact and suffix fits. |
| HOLD_WAIT | Complete return prestate/2squiet/poststate, protected origin retained; at least4.5s after local receipt of valid camera_start ACK; no shortened hold. | Guard failure => latch. Host loss alone => safe-return branch below. |
| HOLD_ACK | Host camera_end metadata and >=120 progressing sensor frames; local hold-end/native/state/collision qualification. | Bad camera evidence => optics failed, not success; local target safety rechecked before safe return. |
| RETURN_DISPATCH | Fresh full protected-origin dispatch guard/collision/state and PRE_GUARD; the selected explicit admission policy (normal requires qualified return suffix). | Latch; no blind15. |
| RETURN_CHILD | Unchanged return15 writer; E/C/S/W/tail/ESD complete. | Latch and reboot-only. |
| RETURN_QUIET | Full fresh pre/quiet/post and>=2s, retained native reference and S. | Latch; no read. |
| RETURN_P85 | Unchanged long3; all child gates and exact [21,0,0]. | Latch; no C1. |
| RETURN_C1 | Unchanged bounded C1; all child gates and exact [0,0,96]. | Latch; no disarm. |
| DISARM | Complete local return proof; exact owned SHORT60 disarm verified before expiry; OVERALL600 remains armed. | Unknown disarm => unresolved, no repeat writer; preserve/reconcile watchdog and reboot policy. |
| LOCAL_RETURNED | Persist immutable completed receipt; host audits independently. | Host loss => awaiting audit/camera cleanup, never RUN_COMPLETE. |
| FINAL_CAPTURE_AUDIT | Host full return hold and metadata, camera stop/collection, hardware/source/receipt audit; no offline FFT wait. | Camera-only failure sets optics_invalid/cleanup_pending; hardware/source/receipt contradiction enters HOST_AUDIT_REJECTED. |
| HOST_AUDIT_REJECTED | Set target_uncertain=true permanently for epoch, reject normal completion; same-target verified reboot before any settings restore. | Preserve recovery ownership/watchdogs; no readoption of local SUCCESS. |
| RESTORE | Verified no child alive; clean audited return OR independently verified changed-boot recovery; restore exact original target settings/DBV/logger/ESD and owned scratch. OVERALL600 ends only by existing restore/recovery contract; release mutex last. | Retain recovery record and cleanup_pending; never wait for offline optics with modified settings/lock/watchdog. |
| OFFLINE_OPTICAL_REVIEW | After guarded restore/cleanup: actualPTS, central encoded60, FFT/optical review of retained files. | Failure sets optics_invalid. Cannot clear degraded classification, target_uncertain or missing ACK. |
| COMPLETE | Normal protocol only; audited target proof, final capture, restoration, cleanup_pending=false, offline optics passed and no sticky failure. | Terminal; no restart/replay. |
| UNCERTAIN | Sticky local failure latch; prevent all child dispatch, preserve watchdog/owner/evidence. | Same-bound reboot only; no15/page0, no log reacquisition to erase failure. |
| RECOVERED_BOOT | Independently verified same target with changed boot, no stale child; existing guarded recovery/restore. | Cannot verify => pending recovery, no cleanup/disarm shortcut. |

## Camera ACK and disconnected return decision

ACK schema must bind manifest digest, experiment epoch, target boot, camera identity,
stage, phase nonce, monotonic sequence, recording-session ID, exact requested and
observed profile, request/result settlement, frame-count/timestamp continuity and
exact metadata result reference. End ACK must reference the accepted start ACK and
same recording session/profile with >=120 advancing sensor frames. Accept
once in the expected state; duplicates/out-of-order/stale boot are refused. Only the
host camera adapter produces ACK after actual metadata checks. On-device receipt
time is not sensor time, and an ACK is not encoded-frame/PTS proof. Start the
local minimum4.5s hold from local receipt of valid camera_start ACK, conservatively
after its actual metadata completion. Do not compare fabricated sensor/local clock
origins. Delayed ACK consumes budget and cannot backdate this timer.

Normal path preserves existing ordering. A separately reviewed SAFE_RETURN edge
from HOLD_START/HOLD_WAIT/HOLD_ACK on missing host/camera qualification may proceed
ONLY from fully qualified SHAM_P85, with no target uncertainty/inflight child,
fresh local native/state/owner/boot/ESD/collision checks, complete return-prequiet,
original HOLD_BEGIN protection and enough remaining whole-return budget. It joins
RETURN_DISPATCH with a sticky RECOVERY_DEGRADED_PROTOCOL classification. This
classification never clears, never clears any failure latch and cannot promote the
attempt to normal RUN_COMPLETE. Current analyzers reject recovered/degraded runs;
missing camera ACKs cannot be reconstructed as if received during execution. A
separately reviewed offline reanalysis may assess retained optical evidence under
its own explicit scope, but cannot change this run classification or substitute for
the missing acquisition protocol. Local stock-return proof remains separate.
A target-local4.5 timer cannot satisfy missing camera metadata or120 frames. Safety
return need not wait for an impossible camera ACK; this early-return branch is an
explicit scientific protocol change, NOT unchanged successful optical acquisition.
Any failed local gate prohibits that branch and requires reboot-only recovery.

No new target-side connection to the other phone is invented. Host-disconnect camera
stop/collection is unresolved: record CAMERA_CLEANUP_PENDING, preserve identity and
recording receipt; reconnecting host reidentifies camera and inspects current UI/files
before acting. Do not toggle blindly or report camera stopped. No local run success
can clear this pending obligation. Camera-independent autonomous cleanup would need
another separately designed finite camera-side mechanism, outside this proposal.

## Deadline and failure ownership

Keep host37 cutoff,45 total policy and8 recovery reserve. SHORT60 is the independent
immutable no-renew watchdog. Inherited OVERALL600 covers the larger setup/cleanup
lifecycle and remains until existing restore/recovery completion, including after
LOCAL_RETURNED. Neither substitutes for the other. Local absolute deadline is not a new60s work allowance.
Proposed conservative grant: host starts clock, asks target to record boot-bound
uptime anchor A, receives it at host elapsed E, and grants deadline A+(37-E), rounded
down with explicit clock/quantization margin. A was sampled before receipt, so this
is conservative versus adding37 at target launch; delayed grant only spends budget.
No second grant/renewal. Validate monotonicity, rate assumptions, suspend behavior
and arithmetic bounds offline and later on target; absent proof => no launch.
Host cutoff remains independent. This handshake consumes G and needs measurement.

Two explicit policies; no implicit promotion between them:

1. NORMAL_RESERVED: for every operation, B_current_success is a separately qualified
successful-path cutoff including acquisition/decode/validation; B_downstream_success
covers disjoint remaining successful operations through return and SHORT60 disarm.
Require now+B_current_success+B_downstream_success+J+S_uncovered < local expiry.
UNKNOWN_BOUND for either operand => NO_NORMAL_LAUNCH. Current local costs/cutoffs
are UNKNOWN, so normal launch is impossible today. Unchanged child/envelope nominal
30–38s timeout/kill bounds plus downstream do NOT fit37 and cannot be relabeled as
successful-path bounds. Qualifying shorter successful-operation cutoffs would need
separate review; crossing one selects failure/reboot-only, not guaranteed return.
Do not double-count nested costs or omit slower baseline/max-cap/parser costs.
2. EXPLORATORY_FACTORY15: distinct future stock-only bootstrap, hard-disabled to14,
with explicit unqualified-success-cost accounting. It may measure unknown costs
under unchanged37/45/8 and SHORT60/OVERALL600, but promises NO reserved normal return.
No unknown gate semantics, source/ownership or child result may be bypassed. It is
not an implemented or authorized live mode here. Completion can be recorded as an
exploratory stock sample, never NORMAL_RESERVED readiness/candidate admission.

Absolute failure/host deadlines and nominal child timeout/kill semantics remain
separate from successful-path admission. Timeout, expired budget or unknown child
outcome sets target_uncertain and selects reboot-only, not next-child dispatch or
native cancellation. Retain8s recovery reserve without claiming reboot will finish
inside it. Host37 expiration cannot physically stop the remote child. SHORT60 is a
fallback, not extra work time. Hung kernel/long0 parser panic/DDIC damage may defeat
reboot/watchdog. Camera waits must be bounded; NORMAL reserves its qualified suffix,
while exploratory mode cannot claim such reserve. SAFE_RETURN remains subject to
its target gates and applicable policy; unknown normal costs cannot enable it under
NORMAL_RESERVED. An exploratory degraded stock return, if separately reviewed, is
an attempted qualified sequence, not a guaranteed reserved return.

Local process termination/crash must leave armed watchdog and ownership intact.
No trap dispatches DSI. A reconnecting host first reads/reconciles epoch/boot/process
and receipt; it never launches another sequence into an uncertain old process. A
PID alone is not identity: bind process start/epoch/owner and inspect conservatively.
A restarted supervisor cannot resume. If alive status cannot be proved, apply existing
same-target reboot recovery; do not remove lock or restore while child may live.
Local completed receipt permits audit, not automatic host assumption that all cleanup
finished. Durable receipt guarantees under KILL/power-loss remain to be designed;
missing/torn record must be treated as uncertainty, never reconstructed success.

## Pure offline harness schema (next deliverable; no implementation here)

No shell, ADB, subprocess, launch, installed binary or device access. Model only five
active child enums in fixed order: SHAM15_WRITE, SHAM_P85, RETURN15_WRITE,
RETURN_P85, RETURN_C1. Baseline is a fixture-bound prerequisite, not a sixth child.
Each enum maps to a fixed manifest plan, reserved nonce, factory payload policy and
required E/C/S/I/W bundles. No free-form child/command/kind and no14.

Typed state:
- target_uncertain: sticky boolean. Any unknown/nonzero producer, missing seal,
  target-gate failure or hardware/source/receipt audit contradiction sets it; no
  later SUCCESS clears it. Verified changed boot is a distinct recovery proof that
  permits guarded restore, not a reset to normal execution.
- optics_invalid: sticky boolean for missing/invalid ACK, continuity/profile/frame
  failure, degraded return or failed offline optical review. Target proof stays
  separate. Further independent optical analysis cannot clear epoch classification.
- cleanup_pending: set of typed obligations (target_restore, camera_stop_collect,
  scratch_cleanup, watchdog_reconcile, owner_release). Each obligation persists
  until its own verified completion receipt; cannot be blanket-cleared by local
  return or optics. Unknown result keeps that obligation pending.
- protocol: NORMAL_RESERVED | EXPLORATORY_FACTORY15; classification NORMAL |
  RECOVERY_DEGRADED_PROTOCOL, with one-way transition to degraded.
- cost: Known(nonnegative conservative successful cost, qualification ID) | UNKNOWN;
  fake monotonic clocks, boot-bound grant/expiry, separate short60 and overall600
  lifecycle states; no resetting clocks on ACK/reconnect.

Invocation receipt is immutable: epoch + boot + phase enum + reserved nonce +
manifest/plan identity + actual producer result (Known(rc, stderr bytes) | Unknown)
+ exact published artifact set/identities + seal identity + gate outcomes. Reserve
and consume invocation before modeled dispatch; every receipt belongs to exactly
one consumed invocation. Unknown/nonzero result can never be readopted from a
SUCCESS file, even if other fixture bytes look valid. A completed receipt cannot
be edited to swap bytes, phase, rc or decoder output. Fixture E/C/S/I/W outcomes
are PASS | FAIL | UNKNOWN, bound to that receipt; any required non-PASS forbids the
next child. Model does not claim to authenticate actual live producers or files.

Spent-epoch ledger outlives scratch and mutex cleanup: terminal or attempted epochs
remain permanently consumed in the model and reject relaunch after reboot/restart.
A future durable host/root-backed record and reconciliation policy must preserve
this property; record loss/ambiguity forbids adoption or relaunch. Ordinary cleanup
cannot delete the authoritative spent record. Actual durable storage/sealing and
crash-safe publication remain unimplemented, not solved by this abstract ledger.

Events: reserve, fixture_producer_result, sealed_evidence, gate_verdict, clock_tick,
bound_grant, typed_camera_ACK, disconnect, audit_accept/reject, crash/restart,
verified_changed_boot, verified_cleanup and offline_optical_verdict. Test every
state/event combination including invalid transitions; no event executes work.
The harness checks ordering/latches/receipts/budgets, not hardware feasibility.
Root/shell sealing, real acquisition/rc, state-without-ESD adapter, clock grant/rate
proof and max-cap storage/parser cost qualification remain explicit unsolved inputs.

## Dependency checklist and required offline tests

- [ ] Freeze/review envelope decoder; pin all component interfaces/blobs together.
- [ ] Implement tested source/manifest binding, one-shot root/shell staging and sealed
  acquisition ownership; reject same-epoch relaunch, wrong boot, source replacement,
  symlink/hardlink/rename/concurrent-write races and uncertain atomic publication.
- [ ] Resolve S no-ESD interface mismatch without synthetic evidence; bind real root
  owner predicate, module/panel/identity and real producer status/stderr to snapshots.
- [ ] Port GUARD_TIMING exact grammar/bounds, original-origin stage binding and all
  nonce uniqueness/collision rules; fault every phase before/after each child.
- [ ] Compose E/C/S/I/W using finite manifests: swapped valid same-nonce files,
  stale valid captures, wrong stage, reordered sections, truncated receipts,
  payload≠factory, native transient/tail, log wrap, child success+stderr, cleanup
  failure and missing ESD must all forbid the next child.
- [ ] Fake-clock state-machine tests: every deadline/ACK-wait boundary, late grant,
  clock rollback/suspend/rounding, slow baseline, overlap overshoot, downstream
  reserve and kill grace; preserve37/45/8/60 without renewing either clock.
- [ ] ACK tests: duplicate/replay/epoch/boot/camera/phase mismatch, loss before and
  after each metadata call, delayed ACK crossing return, insufficient120 frames,
  failed actualPTS/encoded60 despite target timer success. No optical success forged.
- [ ] Crash/restart matrix at dispatch reservation, running child, each validator,
  return proof, disarm request/receipt and restoration; no second writer, blind15,
  lock release with live child or deletion of unknown scratch. Distinguish local
  evidence validity from host receipt loss; preserve camera_cleanup_pending.
- [ ] Parser-cost feasibility gate: measure bounded source/staging verification and
  every local decode/semantic gate, including od-to-AWK expansion at maximum admitted
  input sizes, into the prospective suffix/reserve model. Separate host min/median/max
  measurements are not Android qualification or a worst-case guarantee. Removed ADB
  RTT is not net savings until local costs are included. Qualify the entire package
  stock-only before any unknown-value proposal; no physical benchmark is authorized
  by this document.
- [ ] Android capability/timing qualification remains future work: actual awk/stat/
  tr/od/LC_ALL, process lifetime/root-shell transitions, storage expansion, absolute
  clock and suffix costs. Host-only corpus tests do not establish these properties.

Smallest next deliverable is the PURE OFFLINE model defined above, consuming inert
receipt-bound fixtures, fake clocks/ACKs and UNKNOWN costs, not a runnable controller. Review that
harness and staging/clock contracts before any new stock-only live proposal.

Sources: frozen component READMEs/interfaces; p85_batched_envelope.py:57-210;
run_p85_timed_stock_trial.py:29-68,160-207,218-337,339-387;
run_p85_batched_trial.py:80-119,193-201; run_p85_guarded_trial.py:42-65,109-120,
460-480; p85_guarded_trial.py:66-209; stock_c1_sweep.py:119-154.
