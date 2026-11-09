# Offline AA acquisition/video/optical contract

This is a new AA contract, not a P85 report conversion. The existing P85 validators, optical mathematics and private-video contracts are unchanged. No tool here authorizes acquisition, retrieves media or contacts a device.

- aa_acquisition_validation.py is standard-library-only. It checks the three exact tables, source identity, attempts, trace/callback continuity, exact DBV replay, frame-only redraw, measured C1 in all stages, prewriter quiet, camera/session/clock consistency, short37/45/8/60 and overall600 lifecycle, all cleanup and mandatory return hold/postselectors.
- aa_video_validation.py exposes source_evidence, destination_receipt, accept, consume and joined_view. All media inputs are already-held private owned read-only finalized descriptors. Trusted no-concurrent-writer and source-sink facts remain explicit assumptions, not cryptographic custody attestation. Original acquisition bytes are never rewritten.
- analyze_aa_threshold_trial.py calls the existing pure window/Fourier APIs only after AA admission. The command requires original acquisition, separate derived acceptance, externally reviewed source bindings and an explicit no-concurrent-writers assertion. It joins the receipt-derived result to the actual video bytes before probing and verifies identity/digest again after analysis.
- test_aa_video_validation.py uses synthetic reports/bytes and mocked probes only. No saved private video was opened during implementation.

## Offline optical command

Use a private directory containing media already legitimately available to the analyst. Expected source bindings must come from an independently reviewed manifest, not be silently approved from the supplied report.

python3 06-tools/analyze_aa_threshold_trial.py acquisition.json video.mp4 --derived derived-video.json --source-bindings reviewed-bindings.json --no-concurrent-writers --plan --output plan.json

The stock analysis uses --review fresh-review.json --profiles profiles.npz in place of --plan. A fresh new --qualification-output stock-qualification.json freezes a limited stock diagnostic, only after the fixed60-frame algorithm and both stock comparisons meet the fixed5% normalized fine/mean-Y checks.

Candidate analysis additionally requires --stock-acquisition stock-acquisition.json and --optical-qualification stock-qualification.json. Its review template fixes the previously qualified ROI and baseline fine search band. Baseline geometry must be reviewed against those frozen values. A mismatch is inconclusive; the analyzer never reselects geometry/band from B. No live screenshot approval or human handoff is introduced by this offline review.

The pure runtime API is validate_stock_qualification(acquisition, qualification, source). It checks a completed same-version AA stock acquisition, its canonical digest/source identity, the frozen optical analysis identity, ROI/band/algorithm, both sham/return diagnostics for all three ROIs, actual G and prearm phase estimate. It does not provide a guaranteed future latency bound.

## Interpretation limits

The one-shot contrast is AA11→10 in the complete875-byte stock contextual table, then full stock return. Hashes identify the exact fixed programs; only raw offset77 differs. Stock readback markers and returned C1 are limited operational evidence, not direct AA latch proof.

Short active G ends after qualified stock table/selectors/C1/native/ESD and short-watchdog disarm. The mandatory full return hold and postselectors occur afterward under the unchanged overall600 watchdog; posthold failure cannot yield an accepted acquisition. Recorded target-kernel quiet bounds are never equated to host or camera clocks.

Report fine amplitude against BOTH stock controls; retain full spectra and broad residuals. Short ROIs may leave the broad component unresolved. H264 Y is not linear radiance. Conditional timing is not sensor calibration. No physical Hz, modulation depth, comfort, full-waveform equivalence or >=2000Hz claim is produced. A limited5% stock diagnostic is not blanket optical approval.

## Verification

From06-tools:

python3 -m unittest test_aa_video_validation test_analyze_p85_optical test_analyze_p85_timed_surrogate -q
python3 -O -m unittest test_aa_video_validation test_analyze_p85_optical test_analyze_p85_timed_surrogate -q

At the first review freeze:70 tests PASS in each mode (20 AA,50 existing optical). Fault coverage includes sequence, exact program identity, controller returns, replay/redraw, missing/invalid C1, clock mismatch, quiet duration, repeated attempts, budget/cleanup, source/receipt binding, source flags, camera identities, same-size video substitution, qualification tolerance, and candidate frozen geometry. This is offline software validation, not hardware qualification or measured timing.
