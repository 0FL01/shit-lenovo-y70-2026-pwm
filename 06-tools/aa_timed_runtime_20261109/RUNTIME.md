# AA timed runtime checkpoint


## Latest checkpoint: full-table ESD isolation, 2026-11-10

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

Status: offline implemented; independent bounded runtime review PASS. No device,
USB-host, ADB, transfer, commit or push. No source-clean bypass. The uncommitted
worktree is not admitted for a physical trial.

## Frozen review bytes

- run_aa_timed_stock_trial.py: `2a7d32b471a92718386ac2a3ab2b5771d60b234ca9d9976287f9f60c25bb1073`
- host_source_integration_20261109/host_entrypoint.py: `d4b43f0f187a494c8f0def2b8630a8cc96cece212971899db1405b8f6a487946`
- host_source_integration_20261109/inert_source_loader.py: `6dd008a6f9f55b11fbcb43270f9510a659d4f61f8b7fc3ae2c80ab863c41b40c`
- test_run_aa_timed_stock_trial.py: `3bff2122afc53968eee3bc29d8e22929fed40411ada89c05cc8e4df0f8463c9f`
- host_source_integration_20261109/test_aa_source_profile.py: `f91e053147cd6b923fdf39271ac106d628dbb63bb5b0d10ebd9d553b347e7f35`

All paths above are relative to06-tools. Exact runtime-only path sets/new hashes:
../aa_timed_runtime_closure.json. Operator/API guide: ../AA_TIMED_INTEGRATION.md.

## Tests actually run

35 PASS in normal Python and `python -O`:
- test_run_aa_timed_stock_trial: Tests8, SafeGapTests3, EntrypointTests1,
  TargetUIScratchTests2, PreChildGapTests4 =18.
- host_source_integration_20261109/test_aa_source_profile:2.
- host_source_integration_20261109/test_inert_source_loader:15.

Includes real main through fake device transport and actual finalized source
receipt; actual fixed-byte/deferred-module loading; all12 child uncertainty
boundaries; strict native/wire/C1 validators; no next DSI after uncertainty;
pre-child generated-shell gap/prefix/I/O faults causing zero dispatch; target UI
UID2000/owner guards; short-disarm then posthold failure recovery; no-arm slow
baseline; candidate attempt latched before dispatch; source tamper rejection.

Independent reviewer:44 collected tests normal and44 optimized PASS; added
real-shell cat/sha256sum/awk/rm faults all stopped before dispatch. This is not
physical stock/timing/optical admission.

`git diff --check` passed on both changed host integration files.

Legacy test_host_entrypoint + test_combined_integration:53 setup errors, NOT
PASS. combined_fixture.inputs expects pre-transformation source SHA b651f185…
from combined_binding.json, but the already-committed transformed
run_p85_guarded_trial.py is6510baac…; `git diff --quiet HEAD` for that file is0.
Those tests stop before AA/default-route behavior. Neither old fixture pins nor
that existing runner were changed by this slice.

## Stage and disarm order

Each baseline/middle/return: fresh quiet -> full875bytes/75packets/five callbacks
-> exact single3600 native DBV packet -> existing frame-only chooser redraw ->
known A9/9D/DBV selectors -> C1 ->4.5s optical hold -> known selectors again.
Baseline full stock runs under overall600 before short arm. Middle is full stock
surrogate or single AA11->10 table. Return is full stock. Never read unknown AA.

Measured baseline phase estimate+3s planning margin stops before arm if>=37;
estimate is not a bound. Actual same-source full-stock acquisition plus frozen
optical qualification is required before candidate. Camera baseline PNG saved.

Middle+return prehold qualify under37s host cutoff,45s budget/8s reserve and
nonrenewed60s short watchdog. After return full table/wire, replay/redraw,
selectors/C1/native/ESD and no pending uncertainty, disarm short watchdog.
Mandatory returnhold/postselectors remain under nonrenewed overall600. Posthold
failure requires existing same-target recovery; no normal release on uncertainty.
Latent DDIC effects may persist despite markers; physical optical restoration,
exact PWM Hz and future latency bounds remain unproved.

## Narrow pre-child correction

Reviewer found retrospective host trace validation could reject only AFTER a
selector dispatched. Added one remote TRACE_GUARD immediately BEFORE each child:
prior validated event-prefix count+SHA256, reject LOST/failure, accept only exact
qualified native ESD task/caller/rc1 in the new suffix. Fresh exact4 owned root
scratch files; success removes, failure retains until recovery. Generated-shell
and transport-level regressions confirm forbidden gap means zero child dispatch.
No generic infrastructure, arbitrary register interface or return-code whitelist.

Worst service sizes: stock 40,996 bytes; AA10 40,961 bytes; selectors 41,390 bytes; C1 34,507 bytes. Each is below the 65,535-byte cap.
These are offline construction measurements, not physical timing qualification.
