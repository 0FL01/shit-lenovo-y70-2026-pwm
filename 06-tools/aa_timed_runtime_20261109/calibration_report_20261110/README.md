# AA acquisition boot identity serialization correction

Status: offline producer correction; independent producer review PASS, current
source pins updated and affected tests PASS. No device/camera/ADB calls,
video reads, commit, push, evidence repair or candidate admission in this slice.

## Exact failure

The 03f0ed4774052e843e22e03ff85e2997e9293828 stock-only execution completed its
physical sequence and cleanup, but `PreparedHost.finalize -> source_evidence ->
validate_acquisition` rejected its report. The original has 176932 bytes and
SHA256 `a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a`.

`run_p85_guarded_trial.Trial.setup` deliberately omits `boot_id` from the saved
`before` restoration values. AA calibration records the actual in-memory
`self.before['boot_id']`; the strict consumer requires equality with the saved
`before.boot_id`. That field is absent. Synthetic AA fixtures copied the whole
in-memory dictionary and concealed this boundary mismatch.

The only failed predicate in a diagnostic traversal of ALL acquisition checks
is `Missing same-trial semantic/structural redraw calibration`. The traversal
temporarily collects failures rather than raising and discards its return. It
does not establish acceptance. Ordinary strict validation is tested both before
and after that diagnostic and continues to reject the unchanged original.

## Minimal correction

AA overrides setup, calls inherited setup unchanged, then serializes its actual
preflight boot identity into `report.before`. Shared P85 behavior stays unchanged.
No validator, physical operation, deadline, watchdog, DSI, optical condition,
source-clean check or qualification predicate changes. Original restoration
settings remain intact, including this run's native DBV 6438; historical 828 is
not substituted.

The inherited setup regression uses actual setup/settle/metadata logic and
fakes external I/O only. It now checks the boot report field. P85 still omits it.
Missing or mismatched saved boot IDs remain rejected by acquisition tests.

## Historical corroboration, not retroactive admission

The separately retrieved, existing `0019-before-boot.stdout` and
`0183-envelope-return_stock-write.stdout` are checked against their source-bound
event linkage, original acquisition digest, sizes and byte digests. Exact event
records match the original report. The full return envelope parses with the
existing strict length-framing parser. Its BOOT agrees with before-boot and
calibration. No private boot identifier or raw envelope is copied into this repo.

This corroborates the serialization diagnosis. It does not insert a missing
field into the original, create a replacement acquisition, or create a finalized
video receipt. The original remains rejected and immutable. A historical optical
analysis would require a separately reviewed explicit diagnostic projection and
source/receipt model retaining original bytes/digest and executed source03. That
model is deliberately not implemented here. No current runtime repin can make
this historical run a same-source qualification for the modified producer.

## Verification and freeze

Logs in this directory record normal and optimized runs. The saved-report and
raw-supplement replay uses unittest assertions, active under `python -O`.
`replay_normal.txt` and `replay_optimized.txt`: 7 tests each, zero skips.
`runtime_normal.txt` and `runtime_optimized.txt`: 85 tests each, 3 existing skips
for explicitly supplied external scene references. AA-wide logs separately
record the suite and its existing external-scene skip. `git diff --check` passes.

Frozen code/test bytes:

- run_aa_timed_stock_trial.py: f4107234d039606da3b9c3da195832d7a64a4ef1d1eb4c665615d1c928c5394c
- test_aa_inherited_setup.py: d785cb5e855296df55e41d76c37b3436c2e8f3d5668cdeba2c262832fc371dde
- test_aa_video_validation.py: 74457ef3fcfd822867c46ca5dff7cdce61e46c9ed5fbdbd7f6204a5c6fb45449
- test_aa_saved_calibration_failure.py: 548f6a561feb40a30f0dc2999eab5f8b49bcf8ca7ddaf23551f8f0bf9d2dcfa3

Paths above are relative to `06-tools/`. After independent producer review PASS,
the current AA runtime pin and closure were updated. Historical
runtime metadata remains historical and was not rewritten. Current entrypoint
SHA256: e8b46e57909396b7c1cb8d5768290ed6e868f32061a3bb454715285da76be18e.

`source_consumer_normal.txt` and `source_consumer_optimized.txt`: 71 tests each,
zero skips, covering test_aa_source_profile, test_inert_source_loader,
test_aa_video_validation, test_analyze_p85_timed_surrogate,
test_aa_saved_calibration_failure and test_aa_inherited_setup. This source-only
pin update does not admit the historical acquisition or qualify the corrected
producer physically. Current worktree is not committed/deployed by this task.
