# R12 offline operator QA: draft before schema

No device operations; filenames/records and restoration adapter pending operator schema. No claim of complete qualification from this module alone. This module does not infer image classes, access concealed labels or calibrate time/frequency.

Checks: physical camera service id2 and stock client; actual156000ns ISO6400 frameDuration33350000ns skew31824000ns; last request separately200000ns ISO0 frameDuration33333333ns; AE OFF, focus0, full3264x2448 crop, focal1.63999999, stabilization OFF, preview1440x1080. Each bracket requires increasing frame and timestamp, then whole acquisition order must do the same. PNG decoder integrity/dimensions/hash, complete exact roster, hash duplication audit, manifest event ordering to be wired after schema. Screenshot is not identified to a unique sensor frame by bracket alone.

Restoration must compare actual before/after fields and raw state, not boolean receipt alone: target original application, user brightness/mode, min/peak/actual refresh, DC, Extra Dim values including absent keys, HDR/SDR state and dim versus bright policy explicitly; camera original mode/settings, returned stock 2x, AE ON lockOFF and continuousAF with advancing reads as applicable to captured baseline. Claims limited to observed fields; idle-timer reset and unavailable hidden preferences cannot be labelled exact restoration.

Run verdict remains unavailable until raw schema and complete expected roster/return evidence are specified. No field limits may be silently weakened after observing acquisition.

## Adapter fixed before first phase bracket

Expected exactly P00–P05, three captures 0..2 each. Both metadata JSONs must match independently parsed raw results and identities. Missing members explicitly listed; malformed brackets are retained as failures, never replaced. Extra acquisition PNG ordinals and duplicate hashes reject. Each early/late target raw snapshot is compared with target_awake, typed short JSON is checked against raw, source image content area x0:1440/y332:3090 must be identical early→late. This area excludes Android toolbar/status but is not a classification decode.

Return check compares before_r12→target_after observed settings, app, matrix, foreground, target central crop and two advancing restored camera metadata results against camera_pre. DIM/BRIGHT and native changes are explicitly reported, not erased. The supplied restore schema alone cannot prove Expert hidden remembered controls, UI PHOTO mode or exact idle timer; these flags remain false. Extra release readback is supplementary and not yet wired; current framework float/HBM cannot be claimed from missing fields. No full-restoration claim from a boolean receipt.

The first live run correctly returned INCOMPLETE_OR_REJECTED with zero brackets. No assignment.json, HTML patterns, driver or image classes were read. No source/ordering shared with blind analyst.
