# Offline conditional diagnostic: stock-observation-v2-native10s

Code and synthetic tests only. No new actual movie was recorded or analyzed.
One continuous unchanged-stock movie, four adjacent non-independent 60-frame
windows: [30,90), [90,150), [150,210), [210,270). No v1/source03 reinterpretation.

## Narrow reuse

Existing `analyze_p85_optical.validate_pts`, `decode_y` and `fixed_metrics` are
reused. The latter uses `optical_spectrum.analyze_profiles`: frozen q
0.019775390625 cycles/camera-row, Hann, degree2, RMS/(mean Y−16). q is the existing
FFT8192 grid coefficient, never a new selected peak. Fixed left/main/right
[225/255/285,245,20,330] strips; no ROI averaging/reselection. Windows2–4 compare
to window1 with unchanged absolute all-ROI5% arithmetic. It is NOT acceptance.
Private NPZ includes profiles, PTS and per-frame normalized amplitude/mean-Y curves.

Explicit ffprobe stream/container durations, decoded count, endpoints, cadence
and rate must agree. Frozen9..15s duration retained. Delta from native10s is
reported; duration≤15s does not prove the preventive native10s cap implemented.

## Actual diagnostic API

`analyze_actual(capsule_path, expected_source=..., review_path=..., video=...,
no_concurrent_writers=True)` returns (sanitized_summary, private_detail, arrays).
No CLI/device imports, acquisition commands, mutations or runtime permission.

`expected_source` must come from the independently reviewed/frozen launcher
identity {commit,closure_sha256}, NEVER be copied from the incoming capsule.
Caller explicitly trusts no concurrent writers. All input files are owned
regular0600 files in a private0700 directory; no file symlinks or hard links.
The original route requires the capsule created inode. A copied file is accepted
ONLY through the explicit source-bound transfer branch described in TRANSFER.md;
that branch never changes the original capsule identity.

Consumes the concrete `Coordinator.capsule()` schema
`stock-observation-analysis-evidence-v1`: four numbered before,
recording-snapshots, outcome and source-closure records with exact hashes/bytes;
matching source and canonical closure digest; final unchanged boots; source/media
size and digest; actual created inode and complete sink facts. Inputs are checked
again after decoder work. Missing/mismatched source or custody fails closed.
Hash binding is not proof that untrusted records are truthful: the independently
pinned reviewed producer and trusted local filesystem remain explicit assumptions.

Fresh native-Y review is separate: schema stock-observation-v2-roi-review,
media_sha256, complete capsule records_sha256, reviewed_frames mapping for the
12 fixed first/middle/last frames, frozen rois_xywh, reviewer, whole_screen_flat
false, and native_y_noautorotate_inspected/roi_background_content_verified/
fixed_geometry_verified true. These are actual human review attestations, not
automatic content classification. Whole screen is never claimed flat.

Saved controls are rechecked against the existing camera profile, request/result,
geometry/skew, same recording session, advancing sensor/encoder counters and FPS.
Early pair≤1s gives only a conditional snapshot bound, never per-frame proof.
A late pair is accepted ONLY for conditional diagnostics when the writer records
capture_validity_failure early_controls_unbound, recording_observation_complete
true, control_coverage_status unknown_first_window, strict status inconclusive,
plus complete source/custody/stop≤15s/cleanup evidence. Any other error rejects.
No fixed window is shifted to disguise late control coverage.

Every actual summary remains conditional_diagnostic_only, strict acquisition
inconclusive, qualification/candidate admission false, physical PWM Hz null,
regardless of numerical≤5%. No AA10/14, comfort or optical-return approval.

`write_outputs` writes new private JSON/NPZ files0600 in owned0700 directories,
plus an allowlisted sanitized JSON summary. Raw metadata/boots/source details
stay private. Existing files are never overwritten. A partial output failure
may leave already-created files; callers must choose a fresh output set, not retry
blindly. The summary is not an acquisition receipt.

## Verification

python3 -m unittest discover -s 06-tools/stock_observation_analysis_20261110 -p 'test_*.py' -v
python3 -O -m unittest discover -s 06-tools/stock_observation_analysis_20261110 -p 'test_*.py' -v

Synthetic capsule integration mocks ffprobe/extraction; it is not a real video.
Original source03 diagnostics/thresholds and WORKSTATE are unchanged by this work.

## Transfer fallback

USB-host dependency gap is handled by the separately pinned stdlib-only sender
and nc-lab receiver in transfer.py. See TRANSFER.md for exact APIs, immutable
capsule/records, source and fresh destination custody, actual transport exit
requirement and source/timeouts assumptions. No automatic transport or remote
execution occurs. FREEZE_TRANSFER.json records the review candidate source pins.
