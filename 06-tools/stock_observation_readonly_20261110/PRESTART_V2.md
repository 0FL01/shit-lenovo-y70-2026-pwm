# Diagnostic-only revision after an unclassified read failure

Original failed helper SHA256
`5af512cf02640e0813e627d9967439bcc1ed5ef334485f1d53cb73000158c723`
is preserved unchanged as prestart_inspection.py. Parent reported source-only PASS,
read-only exit1 at 2026-11-10 14:20:51 UTC, and a fresh empty evidence child. This
locates failure before the first successful PNG write, but does **not** distinguish
baseline, boot, native/software/scene parsing, initial camera metadata, screenshot
transport or PNG validation. No root cause is inferred from that absence.

New prestart_inspection_v2.py uses fresh `prestart-inspection-v2`, never adopts the
failed child. Its options and source construction are otherwise unchanged.
All fixed device commands, parser hashes, PNG checks, camera guards, source binding
and boot/mode/scene consistency requirements remain intact. Tests compare the
guard/source-construction ASTs to v1 and verify v1's original SHA256. No actual
transport signature bug was established by source audit. No device retry was run
while preparing this diagnostic revision.

Changes are limited to a transparent monitor around the baseline's existing
preflight/host/bind/shell API, explicit stages around supplemental reads/parses,
and a small static exception-family taxonomy. Successful observations and private
PNG custody retain the existing semantics. Parsing may fail earlier before later
unneeded reads; no check is skipped or weakened.

Failure stdout is structured JSON with diagnostic_revision2, stage_code,
reason_code, completed_shell_reads, shell_rc, stdout_bytes, stderr_bytes and
last_shell_stage_code. Counts are bounded by existing transport output caps; no
raw data, error text, serial, boot ID, session token, command or path is included.
The last-shell stage identifies which read its counts describe, even when failure
is in a subsequent parser. A transport exception before a return leaves sizes and
rc null. A returned nonzero rc is reported numerically, never stderr content.

If a valid newly owned evidence child exists, a fresh exclusive 0600 failure.json
contains only this sanitized diagnostic record. Failure to write that receipt
does not trigger a retry or fallback; stdout reports failure_receipt_written:false.
As with successful receipts, disk is before_descriptor_close; final stdout reports
host_cleanup_verified. Created partial PNG/evidence files are retained. Exit1 and
capture_admitted:false remain mandatory for every failed inspection.

Final-close failure is sticky: stage91 never calls close again and never upgrades
host_cleanup_verified after handles may have been consumed. The pre-close success
receipt remains provisional; final stdout reports the failed close. Regression
coverage explicitly models a failing first close followed by a potential no-op.

## Stage codes

- 1: source construction; 10: private evidence open/create.
- 20/21/22: baseline preflight/host/bind; 23: baseline receipt extraction.
- 100 + 2×operation-index + role: exact baseline shell operation, where role is
  target0/camera1 and operation order is boot, target_identity, camera_identity,
  root, panel, module, native, settings, mutex, power, window, foreground, package,
  metadata. Example target root=106, camera metadata=127.
- 30: supplemental before-boots.
- 31/32: before native read/parse; 33/34: before software read/parse;
  35/36: before scene reads/parse.
- 40/41: first camera metadata read/parse.
- 50/51/52: target PNG read/validate/write.
- 53/54/55: camera PNG read/validate/write.
- 60/61: second camera metadata read/parse/progress.
- 70/71: after native read/parse; 72/73: after software read/parse;
  74/75: after scene reads/parse.
- 80: after-boots; 81: state consistency; 82: final serial binding.
- 90: final private inspection receipt; 91: descriptor close.

Reason codes: 1 guard or already-wrapped baseline failure; 2 direct transport or
Linux-association error; 3 OS error; 4 direct timeout; 5 camera metadata validator;
6 request/result not settled; 7 source-construction error; 8 interruption;
9 unexpected exception class. A baseline's own sanitized exception can obscure
the underlying family: stage remains precise, but reason1 is not a claim that
transport succeeded. This taxonomy does not authorize relaxation or blind retry.

Offline tests inject native/software/camera/PNG/baseline/timeout failures, verify
distinct stages and safe counts, preserve raw-error privacy, exercise success,
and verify no new device command or guard relaxation. No live/private input read.
