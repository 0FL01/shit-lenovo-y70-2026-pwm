# AA full-table timed integration

## Current redraw correction (2026-11-09)

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
