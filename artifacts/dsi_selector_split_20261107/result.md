# First selector-split result — 2026-11-07,06:58–07:00UTC

The approved first verifiable step is complete; the PWM research remains open.
**`confirmed-on-target`: page23:A9 alone is sufficient to suppress the observed
fine optical component in this tested context. Page24:9D alone is not.**
This is not a frequency measurement or a>=2000Hz profile.

## Actual operation and readback

[Authorization](authorization.json), [run](run.json), [analysis](analysis.json),
[original video](../optical/pacman_dsi_selector_split_20261107.mp4),
[comparison frames](../optical/pacman_dsi_selector_split_comparison_20261107.png).

Each candidate was applied exactly once, in the approved five-state order.
Each875-byte/75-packet program differed from live OFF by only one native ON
payload byte; no other sequence, combination or value was introduced.
Every state used DBV3600, software120Hz, verified redraw, short readback,
page0/ESD return and a seven-second optical hold. Camera720p/100µs/ISO6400,
AE/AF OFF, focus9.11752701 and stabilization OFF were checked at both ends.

| State | Read23:A9 | Read24:9D | Read00:52 | Fine component / adjacent stock |
|---|---|---|---|---:|
| stock | 0E | 0E | 0E10 | reference |
| A9 only | 8E | 0E | 0E10 | **0.224** |
| stock return | 0E | 0E | 0E10 | restored fine train |
| 9D only | 0E | 8E | 0E10 | **1.021** |
| stock return | 0E | 0E | 0E10 | restored fine train |

The ratios describe a normalized spatial image component around93px, not
physical modulation depth or percent PWM reduction. A9's mean image signal
was1.059× adjacent stock, so the suppression was not simple image darkening.
The broad moving band remained. Neither exact PWM Hz nor>=2000Hz is established.
No claim that A9 is universally necessary, that9D is irrelevant in other
DBV/refresh conditions, or that remaining compensation/lifecycle code can be
omitted from a daily-use profile follows from this experiment.

## Verification

-375 table packets and five unchanged `51 0E10` writes matched the exact
  programs/type/HS/order.15 short reads independently confirmed selectors/DBV.
-25 table-chunk callbacks plus35 read-page callbacks, then one final recovery
  page callback: all61 returned0. Final trace has444 nonnegative controller
  returns. Pre-cleanup profile has60/60/443 hits; final cleanup adds one callback
  to each relevant count. All misses0; no lost events or captured DMA failure.
-No additional logged DSI writes occurred during the five optical holds.
-The original103796146-byte video was retrieved without modification. Numerical
  analysis used original limited-range Y, no display gamma, identical ROI and
  central75-frame windows. The comparison sheet alone uses common gamma2.
  Camera processing, geometric timing and panel temperature are not calibrated.
-Python syntax checks passed; actual runner and offline analyzer completed.
  `check_ddic_stock_latch.reader` was reused with only three fixed short reads,
  native timeout and independent ESD verification. No broad register census.

## Resolved execution issues, not panel failures

The [first preflight](preflight_brightness_failure.json) stopped with no table,
candidate or recording because an already-awake phone retained DBV828 despite
Android brightness52. Ordinary Home →explicit Display Settings restored3584;
the changed preparation then passed. There were zero raw callbacks in that
failed preparation, so neither candidate was repeated.

Post-run [read-only cleanup check](post_cleanup_state.json) found Android52
restored but the direct native override still3600. The separately recorded
[cleanup correction](cleanup_correction.json) restored actual pre-trial3584.
The runner now captures/restores native DBV for an initially-on manual mode;
this correction was verified without repeating any custom sequence.

## Current state and next hypothesis

Full stock OFF restored; readbacks0E/0E. ESD `reg_read`, logger0, own probes/files
removed, Enforcing and persistent KernelSU retained. No reboot, flash, module,
DTBO or persistent PWM changes. Captured temporary policy remains manual52,
120Hz,30-minute timeout, screen awake; true original automatic policy and
Pacman original settings remain due at final session cleanup.

`hypothesis`: A9's high bit selects or bypasses a brightness-dependent emission
regime; this does not identify a pulse-count or period encoder. The two fields
are not forced readback aliases, because changing either left the other intact.
Their exact packing and low-bit roles remain `unknown`.

The next method check is **offline two-dimensional phase analysis of this same
video**, asking whether static panel-row geometry separates camera rolling
shutter phase from panel scanning. Its assumptions and conditioning must be
tested before assigning Hz. No additional device operation is implicit in this
analysis; the completed two-candidate authorization is consumed, not extended.

## Offline spatial-v2 correction and completed 2D audit — 2026-11-07

`reported`, verified from the saved target video: the old analyzer subtracted
the temporal mean of each stage, removing stationary bands. Its table above
therefore describes the **incoherent** component, not total spatial power.
The historical report/video/cache remain unchanged; use the separate
[v2 analysis](analysis_spatial_v2.json),
[v2 comparison](../optical/pacman_dsi_selector_split_comparison_spatial_v2_20261107.png)
and [cross-check](../optical_repair_20261107/spatial_v2_review.json).

| Candidate | Historical incoherent ratio | Corrected total ratio |
|---|---:|---:|
| A9 only | 0.2241833 | **0.2264067** |
| 9D only | 1.0210592 | **1.0214238** |

These are still the normalized q93 image component relative to adjacent stock,
not total optical modulation depth. The selector conclusion survives this
correction. Full spectra retain stationary and moving structure separately:
`total_power = coherent_power + incoherent_power`. Static UI can contribute;
quadratic spatial detrending attenuates broad structure. Stock already contains
the approximately93/46.5/31/23.3px harmonic train; a31px peak is not proof of a
2160Hz fundamental or a verified>=2000Hz profile.

The repair kit is integrated into `06-tools/`, without a competing second
full-video analyzer. Twelve synthetic/CLI regression tests and Python syntax
checks passed. Both saved videos were fully decoded; all14 historical windows
were retained, and the old metric matches the new incoherent term to<1e-12.
The cached reanalysis also matches all five selector windows to<1e-12. Archive
and register audits completed offline. No new panel writes or camera capture.

The previously pending 2D audit is **complete**:
[report](/home/stfu/.cache/opencode-tmp/opencode/pwm-2d-phase-20261107/REPORT.md),
[final result](/home/stfu/.cache/opencode-tmp/opencode/pwm-2d-phase-20261107/final_result.json).
`hypothesis`: phase projection along one physical OLED row removes arbitrary
vertical panel phase if emission is phase-uniform along that row and camera
time mapping is known. Current geometry is nearly parallel (condition number
roughly100–1000), with varying local row slope and unverified sensor/output
mapping. The final analysis preserves stationary stripes, but physical Hz
remain `unknown`. A physical camera roll near90° would improve this method's
conditioning; it has not been performed. This result neither authorizes another
DSI sequence nor establishes that high-frequency PWM is impossible.
