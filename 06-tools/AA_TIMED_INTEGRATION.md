# AA full-table timed integration

## Current protocol: middle optical observation, 2026-11-10

Status: offline implementation, not physical stock or candidate admission.
The explicit `aa_middle_optical_minimal_v1` protocol omits C1 and posthold
A9/9D/DBV selector transactions only in `sham_stock` / `aa10`. Both fields are
exact `not_measured` records, without data, values, trace callbacks, zero-time
phases or a postselector completion timestamp. Baseline and return retain C1
and both selector measurements. Callback totals are 22 / 12 / 22, or 56 overall.

The middle still requires the exact full table and writer ESD lifecycle,
same-DBV replay, calibrated ordinary redraw, before-hold selectors, final
state(3600), full optical hold and camera metadata, native quiet/state/boot/owner
proof, continuous main-trace validation and an explicit end-hold ESD `reg_read`.
The end-hold guard has sticky uncertainty on any failure and permits no fallback
input or DSI. The return writer, mandatory return C1, state, short disarm and
subsequent return hold/postselectors are unchanged. The 37 / 45 / 8 / 60 / 600 s
limits and 1 s scene acceptance deadline are unchanged.

This deliberately removes middle C1 diagnostic evidence (including the prior
sham stock-value check) and posthold selector readback. Candidate C1 previously
had no value threshold. AA readback was never established; its read plane and
latent state remain unknown. Removing these transactions also removes their
page/read perturbations, so a fresh same-source full-stock optical control with
the identical middle policy is mandatory before any candidate. No frequency,
waveform equivalence, comfort or optical restoration follows from register data.
The finalizer, verified video join, analyzer and stock qualification enforce the
new acquisition policy. Old or mixed-policy records cannot qualify.

The same read-only end-hold ESD/trace guard runs in baseline and middle. Its
measured baseline phase includes the actual reads and validation. From that
current run only, project middle = full - C1 - postselectors, return prehold =
full - hold - end-hold guard - postselectors, then add the unchanged 3 s planning
margin. Thus the measured guard is included exactly once in the active estimate.
This is an observation, not a future bound; hard cutoff and recovery remain.

The failed 1eb5c09 control measured middle C1 at 2.164688 s and postselectors at
3.648456 s. Their 5.813144 s gross cost is not a promised net saving. A historical
counterfactual leaves about 6.151813 s at return-C1 dispatch before accounting
for the replacement guard. Actual return-C1 completion, state and normal disarm
were not observed, so this does not prove the new control will fit.

Final author suite: 155 normal and 155 optimized tests, zero skips, including
104 runtime/acquisition tests. The existing five private scene references and
saved ESD regression remain explicit offline fixtures, not new physical proof.
New cases cover both middle modes, mandatory baseline/return measurements,
owner/ESD/native/state/trace failures, caught/late uncertainty, exact callback
counts, estimator guard cost, mixed records and optical consumer bindings.

The current publication contains nine modified files, including the analyzer,
and no new files or raw captures. Earlier sections describe historical versions,
not the current diagnostic policy. The closure lists the exact current source
identities and offline test results; physical qualification remains pending.



## Earlier checkpoint: missing observation data, 2026-11-10

Status: offline correction, not a completed stock qualification. The c2cb9ec
control again stopped after Back. Exact saved 0115 contains a full stopped
launcher dump followed by a SubSettings header and EOF, with no Settings body.
It is neither a complete scene nor proof of a later return. AOSP ActivityThread
handles activity dumps asynchronously and writes no body when the activity
record is gone. This is a possible mechanism, not proof of the target's race:
[ActivityThread.handleDumpActivity](https://github.com/aosp-mirror/platform_frameworks_base/blob/android16-release/core/java/android/app/ActivityThread.java#L5409).

Scene contract v4 adds a missing-only observation layer before the existing
complete parser, only after the single tap or Back. A syntactically valid known
component/PID/user/UID/display header is required. Every available configuration,
lifecycle, fragment and complete or prefix view-tree field is checked against
the calibrated context before missing data can request another read. Missing
an early block cannot hide a later present contradiction. Duplicate or malformed
data, a proven foreign context and explicit access/dump errors remain terminal.
Completely empty output or absent activity identity remains outside this retry
contract. The ordinary scene command merges stderr with stdout using 2>&1,
without a pipeline or exit-code-masking suffix, so rc0 diagnostics cannot vanish.

Incomplete observations contain no scene or digest and grant no input, DSI or
qualification authority. A new complete strict stable expected scene is still
required. Calibration and before-input reads remain strict. The same total 1 s
acceptance deadline and outer 37 s guard apply, including actual read/wait cost
and the existing version-handshake caveat. This does not establish that a later
physical return will occur within that budget. Fresh same-version baseline
measurement and full stock/optical qualification remain required.

Final offline suite: 144 normal and 144 optimized tests, zero skips, including
93 runtime/acquisition tests and all five explicit private scene references.
Tests cover complete-line partial bodies, valid headers at EOF after inherited
shell stripping, later contradictions, malformed duplicates, rc0 stderr errors,
preserved failing exit codes, elapsed/uncertainty latches and at most one tap/Back.
Exact 0115 is replayed through inherited fake-I/O reads using synthetic known
contexts and a synthetic later ready response; no actual C2 return is inferred.
No raw captures are added to the repository. ESD/native/recovery code and the
other generated command sizes remain unchanged. The guarded scene read is
716 service bytes with a conservative 128-character ownership token.

This historical checkpoint used a seven-file publication scope. Older nested publication records below it describe historical checkpoints.

## Earlier checkpoint: bounded scene readiness, 2026-11-10

Status: offline correction, not a completed stock qualification. The 9ee6a9f
stock run completed the baseline table/replay and then stopped after Back.
Its saved 0112 dump has zero resumed activities: only stopped launcher and the
finishing SubSettings page. That page's complete canonical context matches the
same-run opened scene, not the required ready scene. No subsequent physical
return is established by this capture.

Scene contract v3 separates complete scene parsing from stable readiness.
Only after the existing single tap or Back, a complete scene equal to the
same-trial expected or previous context can request another read. Identity,
process, configuration, fragment and the full canonical tree remain exact.
A finished activity is allowed only as the previous source, never the expected
destination. Zero resumed activities require one complete known Settings
context; multiple resumed activities remain ambiguous and terminal.

Ordinary lifecycle, focus, traversal, visibility and input-queue readiness no
longer require an observed Boolean tuple. AndroidX live-view states 2 through 7
include VIEW_CREATED, AWAITING_EXIT_EFFECTS and AWAITING_ENTER_EFFECTS. The source
creates the view at state 2 and destroys it on descent to state 1. This domain
permits only read-only waiting. Removed roots, uncreated/removed/detached/hidden
fragments, destroyed managers, malformed or duplicate fields, unknown scenes,
and transport/permission failures remain terminal. Relevant AndroidX sources:
[Fragment.java](https://github.com/androidx/androidx/blob/androidx-main/fragment/fragment/src/main/java/androidx/fragment/app/Fragment.java)
and [FragmentStateManager.java](https://github.com/androidx/androidx/blob/androidx-main/fragment/fragment/src/main/java/androidx/fragment/app/FragmentStateManager.java).

The strict success predicate is unchanged: a new expected scene must be
resumed, focused, settled and in state 7 before Back or qualification proceeds.
FrameScheduled alone was not a previous success gate and is not a new one.
Calibration and before-input reads remain strict. Pending returns no digest
and does not clear uncertainty or authorize another input or DSI operation.

The total 1 s acceptance deadline, remaining-active-budget clipping and outer
37 s guard are unchanged. This is not a new transport wall bound: the inherited
12 s version-handshake caveat still applies. Every read and wait counts in the
fresh baseline and active measurement. The baseline full + prehold + 3 s policy
uses this same version and path, never an old run or subtracted timing.

Final offline suite: 136 normal and 136 optimized tests, zero skips, including
85 runtime/acquisition tests. Both private scene references are supplied
explicitly. The 9ee6a9f regression rejects 0112 as success, tests its typed
pending state, then uses historical 0107 as a simulated later stable read, or
repeats pending until expiry. This is fake-I/O caller testing, not evidence of
an actual later return. Published fixtures are generated synthetic data; raw
captures remain outside the repository. Tests include duplicate malformed
lifecycle fields, hard guards, caught failures, late results, one-input counts,
single recovery and remaining-budget clipping.

The ESD isolation lifecycle, native/wire/trace checks, recovery and generated
command sizes are unchanged from 9ee6a9f. The closure manifest lists exactly
seven proposed publication files and no new files. Fresh clean-source stock
qualification and optical review are still required before candidate admission.

## Earlier checkpoint: full-table ESD isolation, 2026-11-10

The current AA writer now isolates ESD before the existing two-second quiet
period and keeps it isolated through complete host validation. Success-only
verified restoration replaces the old writer-esd read. No shared transaction,
wire, trace, fast-scene or watchdog guard was loosened. This is bounded
suppression of new checks, not cancellation of an older in-flight check.

Final offline tests: 125 normal and 125 optimized, zero skips, including the
actual pinned Settings pair and the exact saved 65b1139 rejection. The real
source-clean gates still reject the uncommitted worktree. No physical trial,
deployment or candidate admission is implied. The next control remains stock-only.

Current details, lifecycle limits and test logs are in
`06-tools/aa_timed_runtime_20261109/esd_isolation_20261110/README.md` (repository-relative).
Current pins and conservative encoded command sizes are in
`06-tools/aa_timed_runtime_closure.json`. The checkpoint material below is
historical; its older hashes and command sizes are not the current freeze.

## Opening readiness correction (2026-11-10)

Status: offline source correction, not a completed full-stock qualification.
The 686b6ff stock run stopped during baseline opening, before short arm or any
AA10 write. Exact same-run saved snapshots show a stable timeout scene followed
by the same opening scene with traversal scheduled, window focus absent and a
frame scheduled. The only canonical tree difference was an anonymous ID,
`#5` versus `#6`, on the zero-size internal ViewPager2 recycler.

Scene contract v2 normalizes that ID only for the exact observed ancestry:
zero-size `ViewPager2$RecyclerViewImpl` under zero-size named `view_pager`, under
GONE zero-size named `tab_container`. AndroidX ViewPager2 creates this internal
child using `View.generateViewId()`. Named/static IDs, every other class,
hierarchy order, bound and interaction flag remain exact. This is not general
resource-ID removal.

Only while opening the timeout page, the exact observed traversal=true,
focus=false, frameScheduled=true tuple can produce a typed pending result.
Frame readiness comes from the selected resumed Settings Choreographer, never
another activity. The complete canonical scene must equal the same-trial
expected opened scene before another read is allowed. Pending does not return
a digest or authorize Back: a later strict stable match is required. Calibration,
before-tap and return reads keep the previous strict policy. Unknown scenes,
malformed output, context drift and transport/permission errors remain terminal.
No tap or Back is repeated.

The same total 1 s acceptance deadline and outer 37 s alarm remain; the inherited
12 s version-handshake caveat below is unchanged. Every actual reread is charged
to the measured baseline and active window. The baseline full + prehold + 3 s
formula and all other timing, native/wire, selector/C1, return and recovery gates
are unchanged. A new clean-source stock-only run must qualify this version.

Offline tests replay the exact saved same-run stable/pending pair through the
real redraw caller with fake I/O, and test pending-to-stable ordering, one-input
counts, expiry/late/unknown/context/transport recovery, phase restrictions and
neighboring ID/ancestry/visibility/bounds cases. With the explicit saved pair
supplied, 74 runtime/acquisition tests and 96 combined tests pass in normal
Python and `-O`. These tests are not physical timing or optical qualification.
Frozen source hashes are recorded in the closure manifest. The earlier
source/test counts below are historical.

## Earlier redraw correction (2026-11-09)

Status: offline source correction, not a qualified full-stock run or AA10 admission.
Only the existing Settings timeout page tap/Back operation remains. No new app,
framework helper, DSI sequence or transport redesign is introduced.

The failed c26827c stock run measured 51.994797 s for baseline full + prehold + 3 s,
so it correctly stopped before short arm. Its 9.995258 s redraw included four
UIAutomator dumps (initial discovery/scroll plus before/opened/returned).
Neither that timing nor a subtraction from it is used by the new runtime.

Slow semantic calibration now runs once before the baseline writer, under the
existing overall 600 s watchdog. It discovers a clickable, noncheckable timeout
row from fresh XML; pairs ready/opened/returned XML with ordinary shell
`dumpsys activity top`; checks the exact seven timeout labels and Screen timeout
toolbar; and requires returned XML/framework scene to equal ready. Before every
UIAutomator dump, only the guarded owned redraw.xml is removed and absence is
verified. A zero-exit dump that writes no new file is rejected, never treated as
fresh evidence. Timeout, frame-only wire/native and main-trace checks remain.

Every measured stage uses the same fast method: current ready scene -> the
discovered tap -> opened scene -> Back -> returned scene. Actual calibration 02
established DisplaySettingsActivity/DisplaySettings (136 view nodes), then
SubSettings/ScreenTimeoutSettings (150 nodes), then the exact original scene.
The parser selects each activity's own lifecycle before ignoring stopped
launcher/parent records. It binds one resumed/focused Settings activity, its
resumed/visible AndroidX active/added fragment, full ordered view hierarchy,
configuration, process, bounds, resource and interaction flags. Only object and
autofill IDs plus invalidated/dirty frame bits are normalized. Missing,
ambiguous, malformed or unfamiliar states fail closed.

This is calibrated scene identity/structure, not per-stage literal text or
checked-state verification. The independent timeout read remains mandatory.
`wm dump-visible-window-views` was not substituted: AOSP dumpEncoded disables
user properties, while TextView emits its text as a user property, and that
command can omit failed windows while returning zero. Relevant AOSP sources:
`frameworks/base/core/java/android/view/{ViewDebug,View,ViewRootImpl}.java`,
`core/java/android/widget/TextView.java`, and
`services/core/java/com/android/server/wm/WindowManagerShellCommand.java`,
android16-release; target support is separately evidenced by calibration 02.

Read settling allows only the complete known previous scene until the expected
scene appears, with one total 1 s acceptance deadline and no repeated input.
Other scenes and transport/permission/parse errors are terminal. This deadline
is NOT a new end-to-end transport wall bound: the inherited host:version call
still has its own 12 s connect timeout. Late results are rejected, and the
unchanged outer 37 s alarm owns active-window interruption/recovery. A real
inherited-transport fake-socket regression demonstrates a 1.1 s handshake, late
shell dispatch, rejection and pending uncertainty; no ADB behavior was changed.

The prearm formula remains baseline full + prehold + 3 s. Calibration completes
before baseline, whose measured phase map must match the admitted observation;
baseline/middle/return all record the same scene contract. Actual stage time,
including settling, is charged. Unchanged limits: 37 s active, 45 s host, 8 s
reserve, a nonrenewed 60 s short watchdog and a nonrenewed 600 s overall watchdog.
All full-table, native wire, replay, selectors, C1, holds, return/disarm and
recovery gates remain.

The separate sole-operator calibration 02 used one tap/Back with unchanged
timeout/identity/boot and scratch cleanup. Activity reads took
0.058931 s, 0.049979 s, and 0.050905 s; XML reads took
2.159789 s, 2.072103 s, and 2.122430 s.
These are observations, not future bounds or full-stock qualification. Earlier
calibration 01 stopped before navigation/scratch because its private helper
returned an untrimmed identity string; the production runner was not implicated.

Calibration 02 took each activity snapshot after its slow UIAutomator dump. It
therefore establishes stable scene shape, not immediate post-tap/Back fast-path
compatibility. A normal pending traversal or lifecycle transition can still
cause a conservative failure; it is not silently reclassified as a known scene.
The new stock baseline exercises this identical immediate fast path before arm.
No complete fast redraw operation, full G, or optical result is yet qualified.

Offline runtime/acquisition checks pass 67 tests in normal Python and `-O`,
including actual generated-shell stale XML/no-write and removal-failure cases,
calibration semantic/return faults, all 24 redraw uncertainty boundaries, unknown
scene rejection, unchanged timeout/wire/trace gates and comparable timing.
Including source-profile, loader and inherited-setup checks, the combined suite
passes 89 tests in both modes; details are recorded in the closure manifest.
Next physical gate is a fresh clean-source stock-only complete trial; actual
G < 37 s plus unchanged optical qualification is still required before any AA10.

## Earlier integration record (historical)

No USB-host, Android, ADB, transfer, Git commit or push was executed by this slice.
Independent bounded offline runtime review passed. Clean tracked exact-source checks are not
bypassed: the current uncommitted worktree is not live-admitted.

## Callable and source boundary

- Explicit loader selection: `FixedSourceLoader(..., profile='aa')`; default remains
  `p85`. Call byte-loaded `run_aa_timed_stock_trial.main(...)` with the existing
  explicit HostInputs/HostDependencies and verified_sources result.
- `--stock-only` selects the full-stock surrogate. `--aa10` additionally requires
  `--stock-qualification` and `--optical-qualification`, same-source qualified
  full-stock acquisition and frozen limited optical diagnostic. No live handoff.
- Runtime hardware closure: 23 files; AA finalizer closure: 25; complete loader
  snapshot: 27. Exact paths and changed/new runtime hashes are separately recorded
  in `aa_timed_runtime_closure.json`. Tests/docs are not runtime dependencies.
- Original hardware construction, socket transport and retained private-video sink
  remain unchanged. Original source gate runs again; AA adds exact bound runtime
  bytes and dispatches the distinct AA acquisition/finalizer, never a P85 schema.
- Host wiring changes only `host_source_integration_20261109/inert_source_loader.py`
  and `host_entrypoint.py`. The separate builder slice owns the narrow shared
  `dsi_trial_transaction.py` fixed aa10 allowlist addition.

## Actual stage order and boundary

All phases: fresh qualified quiet -> one exact 875-byte/75-packet table in five
callbacks -> exactly one native `51 0e 10` replay (no hidden table) -> existing
Settings timeout chooser open/cancel, zero native DSI -> A9/9D/DBV selectors ->
qualified C1 -> 4.5-second sensor/metadata hold -> same known selectors again.
Baseline is full stock outside short37 under overall600; middle is full stock or
one AA10 table; return is full stock. Unknown AA is never read.

The prearm estimate uses measured baseline phase costs and a 3-second planning
margin. If the observed composition already exceeds37, stop before arm and clean
up. This estimate is explicitly not a latency bound. Only an actual completed
same-version full-stock composition plus frozen optical diagnostic admits AA10.

Middle and return prehold verification run inside unchanged37-second host cutoff,
45-second host budget/8 reserve and one nonrenewed60-second short watchdog.
Candidate attempt is latched before dispatch. Any uncertain child prevents next
DSI/stock/page0 writer and uses the existing same-target reboot recovery only.

Short disarm occurs after full stock transaction/wire, replay/redraw, known
selectors, C1, native state and restored ESD, with no pending operation. Return
hold and posthold selectors remain mandatory under the nonrenewed600-second
watchdog. Posthold failure uses recovery, never normal release. Latent AA/latch
state and physical optical restoration are not proved by these markers.

## Owned lifetimes

Main pwm_mode instance/probes and source-bound root700 chunks are prepared before
short arm. Main trace checks prefix and callback accounting around every child. A bounded
remote TRACE_GUARD binds the exact previous event prefix by count/SHA256 and
classifies the suffix BEFORE child dispatch; host validation is not substituted
for that pre-child gate.
Only the already-qualified exact native ESD task/caller/rc1 is accepted in safe
gaps; writer/selector/C1 operation envelopes remain strict. No generic register
or arbitrary controller-return interface is introduced.

Target UI XML is a NEW independent ordinary shell-owned700 `aa-ui-<nonce>`
directory, token owner600/XML600 with UID2000/no-symlink checks and exact cleanup.
It is not the root700 DSI workdir, a protected producer/receipt path, or a root
fallback. The invalid root-workdir UI path was found during offline review and
was never attempted. Settings timeout checks the setup-derived captured original
(e.g. original30min remains30min); the chooser's10min option identifies UI only.

Baseline PNG is saved before arm. Frozen ROI/band/algorithm/limits come from the
stock optical qualification. Current camera metadata/session remains strict;
metadata is not a geometry proof. Baseline-only optical geometry mismatch makes
the later result inconclusive, never permits ROI reselection after candidate.

## Offline verification

35 tests PASS in normal Python and `python -O`: runtime18, source-profile2 and
original loader15. Runtime uses real envelope, five-block, wire, selector and C1
validators with fake device I/O, including real main through source_evidence.
Faults cover all12 child transport boundaries, callback failure, return-posthold
failure after short disarm, slow baseline no-arm/no-reboot, candidate latch,
exact ESD gap versus operation/caller/task/rc/loss rejection, UID/owner UI guards, generated remote pre-child prefix/I/O faults with zero
child dispatch,
actual fixed-byte module/finalizer load and deferred source tampering.

Worst encoded command service sizes: stock40996, AA10 40961, selectors41390,
C1 34507 bytes, all below65535. These sizes are offline construction evidence,
not physical latency or success evidence.

Legacy combined/host-entrypoint suites were attempted:53 setup errors stop at a
historical fixture pin mismatch for unchanged run_p85_guarded_trial.py, before
AA/default route tests execute. Their historical pins were not rewritten and
these suites are not claimed passing. Original loader suite does pass.

Independent reviewer also ran44 collected tests in normal and optimized Python,
plus real-shell cat/sha256sum/awk/rm fault injections before dispatch, all PASS.
This is not actual stock timing, optical qualification or device admission.

## Selector boundary correction (2026-11-10)

Current selector CHILD ends with exact ESD_HELD mode5 readback. Runtime retains
mode5 through full envelope/trace/values/native/state validation, saves the
validated pre-restore cursor, and only then performs verified success-only host
restoration. pending_read remains sticky until success; panel_uncertain remains
owned by the enclosing phase. The new aa_selector_esd_isolation_v1 lifecycle is
mandatory for acquisition and stock qualification; legacy restored-child evidence
is not interchangeable. Extra operation events remain failures, including an
already-in-flight ESD check. No timeout or watchdog limit changed.

Current verification and command sizes supersede the historical numbers above:
see aa_timed_runtime_closure.json selector_esd_isolation_correction and
[boundary review](aa_timed_runtime_20261109/selector_esd_isolation_20261110/REVIEW.md).
The synthetic boundary proof does not diagnose saved0171. Actual failure cause
remains unknown, and physical retry/stock qualification remain on hold.
