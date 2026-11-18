# R12 prospective local geometry witness

Frozen using only archived R11 `short3` and four archived short-exposure frames, before viewing R12 images. No device actions. This is a local nearby-structure check, **not four-corner/full-display registration**, and must not be used to call an A/B pair pixel-registered. No pixel-time calibration, kinematics, frequency, PWM, linear-light or physical-amplitude inference.

Two fixed rectangles, in original 1080×2392 RGB preview coordinates: [920,915,974,965] (upper-left rounded boundary), [988,918,1053,975] (upper dark notch/boundary). They are above the changing spatial code; static-code changes must not modify this upper scene. Reference patches are archived R11 short3. Search integer translations −6…+6 in each axis, pick maximum ordinary mean-RGB zero-mean NCC; exact tie breaks lexicographically descending dx then dy. Each must have NCC≥0.90 and |dx|,|dy|≤2. No fitting/warp of signal samples. No prospective per-frame template updates. Two local textures do not constrain the complete affine/projective field. Repeated texture, content changes, exposure/ISP changes or blur can fail or confound this witness. The subpixel position is not estimated; the threshold is a local engineering veto, not a calibrated confidence bound.

Independent headroom veto: all 2944 unique four-integer-neighbor support pixels of the existing frozen R10 bilinear sampler must be <250 in every channel. These are not 2944 independent signal samples. The sampler has1600 fractional locations and1280 integer centers strictly within central40% cell windows; neighbors extend beyond the windows. No black-floor veto is invented: report each zero-channel count and any-zero as warnings. This upper-headroom gate says nothing about sensor clipping or linearity. Separate signal code/contrast and Camera2 guards remain required. In particular archived short2 passes geometry/headroom while failing the old fixed-A threshold at58/64; **this does not rehabilitate it**.

## Replay without publishing photographs

`python -B replay.py --reference "$R11/short3.png" "$R11/short_drag.png" "$R11/short2.png" "$R11/short3.png" "$R11/short4.png"`

Compare stdout byte-for-byte to `archive_validation.json`. The user supplies the private original reference; no hardcoded bench path and no sensor/camera image or patch is included here. `replay.reference(path)` validates the exact PNG hash, reconstructs both original NumPy patch files in a temporary directory, verifies their original hashes and deletes only its own temporary files on exit. It restores the module data directory on exit. This context uses module state and is sequential, not thread-safe. It never rewrites supplied input or frozen repository files.

`python -B test_replay.py "$R11"` and `python -OB test_replay.py "$R11"` run eight tests, including sixteen whole-image four-pixel translations. Wrong reference, modified reconstructed template, wrong dimensions, black image, overexposed archived auto frame and code-region replacement are tested. Archived short2 still passes this local witness but fails separate fixed-A signal threshold58/64; no rehabilitation.

`original_geometry.py` is byte-for-byte the prospective frozen code, merely renamed. Its original standalone CLI expects private patch dependencies alongside it; use the wrapper CLI in this publication instead. Preserved hashes:

- Original geometry: `9fec33994c4f46e773f58f6099c99365f6b79179e85ff3dfc575bc866adc9c28`
- Freeze manifest: `9dbee9c74ab13379155516aebcb855adc676b9c7ca47fe2f58db4edff30d4aa8`
- Exact R10 transform: `952bde8317f3fe1227719dc042bff16ec8e72bd826301ba8ca712b7276b4f631`
- Original R11 reference PNG and both NumPy patch hashes: in `freeze.json`.

All four archived short frames pass. All sixteen tested rigid translations ±4 pixels fail. These are development/archive checks, not prospective R12 validation and not a proof of full projective registration. No R12/R12b frames were opened for this package or used to tune it. Any future replay must report rejected and accepted frames without changing these criteria.
