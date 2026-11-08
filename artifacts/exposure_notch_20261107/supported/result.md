# Exposure-notch control — measured minimum and rebound, no PWM increase

`confirmed-on-target`,2026-11-07 08:17–08:22UTC. One changed-method stock optical
control completed: actual camera exposures100/500/1000/1428.571/2000/100us,
constantISO1600, targetDC0/nativeDBV3600/software120. All request/result values
matched; focus/crop/skew/zoom/AE-AF/stabilization stayed fixed during recording.

Evidence: [run](run.json), [analysis](analysis.json), [frames](comparison.png),
[original229412899-byte video](../../optical/pacman_exposure_notch_supported_20261107.mp4),
[cleanup](post_cleanup.json). Reproducer: [../analyze.py](../analyze.py).

## Observation

Spatial-v2 on original limited-range Y, identical60×500 ROI and six central75-frame
windows, no temporal mean subtraction. Ratios below are total q93 component
divided by meanY−16, relative to the average of bracketing100us controls:

| Actual exposure, us | q93 normalized image ratio | MeanY−16 |
|---|---:|---:|
|100 initial|0.9766|4.7815|
|500|0.8891|23.2530|
|1000|0.3403|43.0968|
|1428.571|**0.0328**|56.9376|
|2000|**0.1725**|72.9943|
|100 return|1.0234|4.8639|

The fine component has a pronounced integration minimum near1.43ms and recovers
beyond it at2ms. Higher spatial harmonics are also attenuated near the minimum;
the500us third-harmonic ratio is0.0726. Baseline return is within~5% for normalized
q93; this is repeatability of image codes, not a physical-Hz error bar. Broad
structure remains visible; no low-frequency-envelope clearance is asserted.

`hypothesis`: this pattern supports the previously considered~720Hz fine
component more strongly than~1440 or2160Hz under the ideal integration model.
For example, ideal720 predicts q93 ratios0.807/0.344/0.028/0.219 for
500/1000/1428.571/2000us;2160 predicts0.079/0.077/0.030/0.067. Actual ratios
are not an exact photometric fit. The first-stage mean signal is small and
the longer exposures show non-linear camera-code response; ISP/noise/black level
and static content matter. A single minimum also has integer-period ambiguity.

**No calibrated physical PWM frequency or>=2000Hz result is declared.** This
experiment changed the camera only, not the panel emission program. It directly
demonstrates why disappearance of camera stripes alone cannot prove a PWM fix.
The useful new constraint is an exposure-time minimum plus rebound, independent
of translating camera-row spacing into Hz. It can help distinguish later large
frequency-change candidates from mode/brightness-only effects.

## Validation and resolved method issue

- All5939 frames decoded. Source PTS strictly increasing; each analysed window
  contains75 frames. All full spectra satisfy total=coherent+incoherent power;
  ROI saturation fraction0 at every exposure. Comparison frames inspected.
- Six exact same-DBV native writes `51 0E10`; no logged writes during any hold,
  no DC-param/PCD callback or unexpected timing program.33 controller returns
  nonnegative, zero misses/lost events or captured DMA errors.
- The default rawvideo encoder timebase emitted two output-DTS warnings despite
  strictly increasing source PTS. The decoder now explicitly uses input timebase
  (`-enc_time_base demux`). A second full decode produced no stderr and **all5939
  frame-row profiles are bit-identical** to the first; numerical reports were
  not overwritten. [Timing validation](decode_timing_validation.json).
- The preceding [aborted run](../run.json) stopped after100/500us when the camera
  UI could not select700us within5%; its [validation](../failure_validation.json)
  confirms cleanup and retained partial video. The new1000/1428.571/2000 bracket
  changed the method rather than weakening the tolerance or claiming a panel
  negative. Reset-before-tap and repeated native-value verification address the
  observed SeekBar thumb hit-testing behaviour; no blind coordinate-only claim.

## Current boundary

At08:28, independent read-only checks confirm UID0/Enforcing, stockDC0,
ESDreg_read/logger0, captured manual52/nativeDBV828/requested120/30min policy,
own probes/instance/UI files absent. Camera restored100us/ISO6400/manual focus,
AE-AF/stabilization OFF; remains prepared/awake. Original pre-investigation
policies remain due at final session cleanup. No custom DSI, flash, reboot,
kernel/module or persistent PWM change in either notch attempt.

R3 remains active. The owner's2–3× large-increase direction is unchanged. The
offline-validated [S0C1 coarse control](../../dsi_coupled_on_20261107/proposal.md)
still awaits **exact operation approval**, including its emergency ordinary
reboot return. General damage-risk acceptance does not silently authorize that
new table. No capture/subagent job remains running; do not repeat these stock
controls as a solution, and do not label the prepared table a numeric multiplier.
