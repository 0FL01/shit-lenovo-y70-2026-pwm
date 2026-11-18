# R12b frozen local-structure replay

Run only after the parent reported blind prediction sealing with SHA-256 `c3c353e34585c4e4b4bc60d16586d813219bc1372a9a2714f23f09e3b1a56079`. This geometry-only analysis received 18 ordinal previews, no stimulus label map. No device interaction, new reference selection, fitting to the capture, threshold adjustment or rejected-frame removal.

**15/18 pass the local witness; three failures must remain failures.** All 18 pass upper headroom. This does not validate the whole acquisition or override the separate signal/Camera2 guards.

| Ordinal | Patch0 NCC | dx,dy | Frozen rejection |
|---|---:|---:|---|
| p02_3 | 0.8677815881454838 | 1,0 | NCC <0.90 |
| p04_1 | 0.8599037537080609 | 0,0 | NCC <0.90 |
| p04_3 | 0.9216464900110813 | 3,0 | absolute dx >2 |

All three have patch1 passing. A low NCC or best-match shift is a local texture mismatch under this method, not independent proof that the physical phone moved or blurred. No rehabilitation based on human appearance is performed.

Across all18, patch0 NCC0.8599037537080609…0.9714430394843255, dx−1…3, dy0. Patch1 NCC0.9517859099536015…0.9970353376646873, dx−1…1, dy0. Every ordinal's exact results are in `actual_capture.json`.

On the fixed2944 integer-neighbor support per frame, global RGB minima[4,0,11] and maxima[92,96,122]. All values are below250. Green-channel zero-floor warnings occur at p01_3 (3 pixels) and p06_1 (18 pixels); red/blue zero counts are0, and all other frames have no zero in any channel. These are image-support counts, not sensor-clipping or optical-linearity measurements. The2944 neighbors are distinct from1600 fractional sampling locations and1280 central-window integer centers.

Full-display/projective registration remains **unknown**, even for the15 passing frames. Only two nearby static structures are checked; this provides no pixel-time calibration, kinematics, physical amplitude, PWM or frequency measurement.

## Reproduce

`python -B capture_replay.py --reference "$R11/short3.png" "$BLIND_CAPTURE"`

This requires exactly p01_1…p06_3 and18 distinct PNG byte hashes. Compare stdout byte-for-byte with `actual_capture.json`. Files stay private; no local paths or photographs are included here.

`python -B test_capture.py "$R11/short3.png" "$BLIND_CAPTURE"`

Repeat with `-OB`. Four tests passed in both modes: exact raw replay and explicit expected failures/counts/floor warnings; missing ordinal; extra PNG; duplicate ordinal content. Eight earlier archive tests also passed normal/−O. Original prospective code and dependency hashes are unchanged.
