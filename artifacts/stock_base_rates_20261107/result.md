# Stock base-rate control: executed, not a PWM solution

`confirmed-on-target`,2026-11-07 07:31–07:33UTC. The one-shot native
120→144→120→90→120 sequence completed before the owner's subsequent direction
to avoid small frequency-increase steps. No replay/custom DDIC program, register
read/page-selector operation, ESD disable, reboot or flash occurred.

Evidence: [run](run.json), [analysis](analysis.json), [frames](comparison.png),
[original video](../optical/pacman_stock_base_rates_20261107.mp4),
[post-cleanup check](post_cleanup.json). Implementation is the new `--base-rates`
branch of `06-tools/capture_ui_dc_reference.py`; `analyze.py` reproduces this
specific offline validation. Do not rerun the completed hardware sequence.

## Native and optical findings

- DC0 and DBV3600 throughout; each stage had the same verified stock chooser
  open/cancel redraw and7s hold. Camera100us/ISO6400/AE-AF OFF/focus9.11752701,
  stabilization OFF, crop/skew/zoom metadata unchanged.
- All62 timing packets match exact live DT payload/type/LP/order. There were10
  identical HS brightness writes `51 0E10`, plus one128-byte DSC PPS equal to
  the previously captured stock transition. The90Hz path passed through idle
  timing@7 before timing@2; it is accounted for, not mistaken for90Hz operation.
- Final trace:85 nonnegative controller returns, zero probe misses/lost events;
  no captured DMA error, DC-param or PCD callbacks. No logged writes during holds.
- All2845 original frames decoded from110159667-byte video. Five central75-frame
  windows, same60×500 ROI, full spatial-v2 spectra; total/coherent/incoherent
  partition verified. Comparison frames inspected; no saturated ROI pixels.

| Requested and observed base | Strongest fine spatial peak, pixels | Sampled temporal phase alias, cycles/s |
|---|---:|---:|
|120 initial|94.16|1.351|
|144|87.61|1.311|
|120 return|93.62|1.337|
|90|92.56|1.281|
|120 return|92.56|1.302|

The spatial harmonic train shifts at144, but not by144/120.90 does not yield
the125px spacing predicted by naive proportional scaling from120. Returns
recover the original class. The roughly93px first peak has broad-background
bias; higher harmonics give a more stable train estimate. Zero padding is
interpolation, not new physical resolution.

[Temporal diagnostic](temporal_alias.json), reproduced by `temporal_alias.py`,
fits complex coefficients without temporal demeaning. Harmonics2–4 show
consistent multiples of the observed~1.3cycles/s drift. Synthetic stationary
and signed-drift checks pass. **These are30fps sampled aliases, not physical
PWM frequencies.** Integer cadence branches, source harmonic order and camera
mapping remain unresolved; residuals are not physical-Hz confidence intervals.

`hypothesis`: native base changes alter spatial scan phase while retaining a
similar temporal carrier. A carrier difference by an integer multiple of camera
cadence can also fit these data. Thus unchanged alias is not proof of unchanged
Hz. The simplistic use of refresh or pixel spacing as a PWM multiplier is not
supported; no>=2000Hz claim follows.

## State, checks and next scope

Before preparation the already-awake phone had dimmed nativeDBV828 despite
Android52. Home/Settings restored the active preparation; the experiment used
3600. Finally the **captured initial828** was restored and independently checked,
not incorrectly reported as the earlier session's3584. Android52/manual,
requested120,30-minute timeout/stay-on7, DC0/logger0/ESDreg_read, UID0 and
Enforcing retained; own probes/instance/UI files absent. Pacman remains prepared
and awake as requested. Original pre-investigation policies remain due at final
session cleanup.

Python syntax checks and all12 optical unit tests pass; pre-run independent
review found no blocking issue. Actual native packet and cleanup checks above
were performed after execution, not inferred from review.

Owner now directs approximately2–3× proposed frequency changes, forbids small
incremental increases, and accepts panel destruction (`reported`; recorded in
the execution contract). This stock control is **not** such an increase and
will not be repeated as a solution. Next work targets a large, falsifiable
EM-period/count change, not a refresh tweak. A raw-byte multiplier is not a
frequency multiplier; a new composed DSI program still needs its exact proposal
and separate confirmation. R3 remains active, no hardware-impossibility claim.
