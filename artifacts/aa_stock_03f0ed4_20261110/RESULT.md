# Source03 full-stock control: execution complete, acquisition rejected

Evidence status: **confirmed-on-target** by saved runtime records and separate
read-only postflight; physical PWM and optical restoration remain **unknown**.

Executed source: `03f0ed4774052e843e22e03ff85e2997e9293828`, research branch
`research/aa-threshold-20261109`. Source-only deployment covered 32 verified
files (verified code-only deployment receipt). One unchanged retry followed a denied
launch confirmed not executed and explicit authorization. That retry allowance
is consumed; it does not authorize another operation.

## Execution and independent restoration

- Baseline, sham_stock and return_stock completed; each runtime stage qualified
  its complete stock table with 75 matched native packets, 225 total.
- Observed active G = 33.46979668410495 seconds, below the unchanged 37-second
  limit. G covers the middle and return active window through short-watchdog
  disarm, not the whole experiment. This observation is not a future timing bound.
- Explicit full-stock return, mandatory return hold/postselectors, original
  settings/DBV/logger restoration, camera stop, watchdog disarm and mutex release
  were recorded. No AA10, P85-14 or recovery reboot occurred.
- Actual saved originals: brightness 98, manual mode 0, minimum/peak 120.0 Hz,
  timeout 1800000 ms, native DBV 6438, logger 0. The previous run's DBV 828 is not
  substituted; the reason for the inter-run difference is unknown.
- Independent read-only postflight concluded at 12:26:31 UTC on 2026-11-10:
  root/identity/module checks passed, Enforcing, native DBV 6438 / power 0 / DC 0 / logger 0,
  all five exact settings restored, mutex absent, camera stopped in PREVIEW.
  Final pinned-server association passed. This is not unique-holder proof or
  physical DDIC/optical recovery proof.

Independent saved-evidence review reproduced these facts and the G calculation.
This is the saved 12:26 observation, not a new current-device check.

## Post-execution report contract failure

After execution and cleanup, `PreparedHost.finalize -> source_evidence ->
validate_acquisition` rejected the original with
`Missing same-trial semantic/structural redraw calibration`.

The inherited P85 producer omits boot_id from saved report.before. AA calibration
contains the actual preflight boot identity, but the strict consumer compares it
to the absent saved field. A diagnostic evaluation of all acquisition predicates
found only this failure. That diagnostic is not an accepted acquisition.

The original remains unchanged: 176932 bytes, SHA256
`a2875aba1a9c7446eadb2272f3f6ed8c975d4ac50c183a193c9e2a1eb86a268a`.
Separate source-bound saved before-boot and return-envelope BOOT agree with
calibration. They corroborate the diagnosis; they do not repair or replace the
original report, create a receipt, or grant qualification.

## Correction and remaining work

The independently reviewed minimal AA setup override now serializes the actual
inherited preflight boot identity. Shared P85, strict acquisition/video consumers
and physical guards remain unchanged. The current source pin and closure identify
the corrected producer, not the historical source03 execution. The edited producer
has not been physically tested or deployed by this work.

After pin update, 71 affected source/profile/loader/consumer/replay tests passed
in normal Python and 71 in optimized Python, with no skips. Earlier producer
regressions: 88 AA tests per mode (one external-scene skip), 85 runtime tests per
mode (three external-scene skips), exact replay/inherited setup seven per mode
without skips. Details and frozen hashes are in
`../../06-tools/aa_timed_runtime_20261109/calibration_report_20261110/README.md`.

The 96,172,619-byte video remains private on the USB host and in a separately
verified private analysis copy. It was not read by this correction task. A separate
offline diagnostic is in progress; no completed optical analysis or qualification
exists at this checkpoint. Transfer byte integrity was verified, but historical
created-inode custody is absent; transfer does not establish qualification.
Historical diagnostic analysis requires a separately reviewed explicit source
and receipt model retaining the original bytes and historical source. No AA10
admission, exact PWM Hz, >=2000 Hz success or new physical-trial allowance follows.

Machine-readable sanitized facts: [summary.json](summary.json). Private raw
identifiers, boot IDs, screenshots and captures are intentionally not published.
