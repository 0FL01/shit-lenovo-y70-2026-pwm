# AA full-table timed integration (offline implementation)

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
