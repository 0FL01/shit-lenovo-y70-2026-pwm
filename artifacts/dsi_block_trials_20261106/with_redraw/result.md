# Corrected-method results — 2026-11-06 22:24–22:27 UTC

`confirmed-on-target`, restricted to this tested condition: changing ONLY the two
high-byte payloads `23:A9 0E→8E` and `24:9D 0E→8E` in the complete live OFF program,
then performing the verified redraw, suppresses the fine image-band train atDBV3600.
Stock before and after retains it. The broad moving band remains. **No >=2000Hz or
usable PWM fix is established.**

## Evidence and scope

- [Authorized night series](authorization.json), [actual run](run.json),
  [reproducible offline analysis](analysis.json),
  [original video](../../optical/pacman_dsi_blocks_redraw_20261106.mp4),
  [nine-frame comparison](../../optical/pacman_dsi_blocks_redraw_comparison.png).
- Each candidate once, nine7s holds. Every table875B/75packets unchanged except the
  specified1/2/11/10 bytes; after every table one native `51 0e10` and a settings
  chooser open/cancel with no preference selection. DBV3600/software120Hz;
  Camera2 actual/request100µs/ISO6400/AE-AF OFF/manualfocus9.11752701, stabilizationOFF.
- All675 table packets independently rechecked for payload/type/HS/order;45 callbacks
  return0;803 controller returns are nonnegative; all probes0misses, no lost trace or
  captured DMA-completion error. These software checks do not constitute panel ACK.
  An additional bounded parse from each table END through its redraw/hold snapshot
  found only the expected `51 0e10`, with no other logged vendor command in all9 states.
- Video178509912B,4617 decoded frames,153984ms MediaStore duration. Analysis uses
  original limited-range Y, ROI[540,190,60,500],75frames per central2.5s window.
  Windows use a coarse record-tap origin with margins inside7s holds, not exact sensor
  timestamps. Parent inspected all nine comparison frames: no chooser remains in the
  sampled holds, and the threshold stage alone loses the fine train. Equal gamma2 is
  used only for viewing, not quantitative analysis.

## Outcomes

Ratios compare each candidate with the average of its adjacent stock intervals.
They are image-code quantities, not calibrated luminance or modulation depth.

| Candidate | Normalized fine-component ratio | Mean image-signal ratio | Observation |
|---|---:|---:|---|
|23:80=90|0.981|1.005|Fine train retained, period near94 camera pixels|
|23:A9/24:9D=8E|**0.392**|1.054|Fine train suppressed; broad band retained|
|53:95/A2 nativeON|1.072|1.001|Fine train retained|
|63:F2/F3 nativeON|1.002|1.006|Fine train retained|

Stock windows have fine-component periods92.6–94.1px; these are NOT hertz. The
threshold state's spectral maximum hits the search boundary: no invented period
is assigned. Raw pixel maxima45–48 for other stages and47 for thresholds; noY>=235.
There is no independent panel-temperature or calibrated photometric measurement.

The first mode90 experiment, before redraw was understood, showed lower image
signal. That result cannot be promoted to a stable mode90 brightness effect: after
the corrected application step, this series does not reproduce that dimming.

## What is now isolated

- The **pair together is sufficient** for the observed fine-to-broad change against
  the OFF background. Neither member has been tested independently. It does not
  prove both are necessary, that they are mirrored registers, or their exact layout.
- The other32 changed packets of the complete factoryON set are not needed for this
  particular fine-train suppression. They may still matter for compensation, colors,
  lifecycle or other conditions; this is not permission to omit them in a daily profile.
- The outcome resembles the previously observed whole factoryON effect; it does not
  establish identical waveforms or eliminate the remaining lower-frequency component.
- The other three isolated substitutions do not supply a useful frequency increase
  in this condition. This does not prove those fields never affect emission timing.

## Conditional decoding: not simply a larger unsigned threshold

Existing evidence: stock `0E11` is3601; standard DBV3600 gives fine bands,3601 gives
sparse broad bands. The current two-byte edit changes the putative words to`8E11`
(36369), while DBV3600 now gives the sparse pattern.

Under the explicit model “unsigned16-bit threshold T; fine mode if DBV<T, no other
semantic changes”, raising T from3601 to36369 predicts **fine**, contradicting this
observation. That simple model is insufficient **if these adjacent bytes form T**.
It does not decode the real registers: a control flag, signed representation
(`8E11` interpreted as int16 is−29167), changed comparison direction or another
layout can all explain this limited observation. No signed encoding is asserted.
The unchanged low15bits/ALS3601 coincidence remains evidence for a threshold-related
mechanism, not an EM-count/divider formula. Increasing these words to “2160” would
therefore have no demonstrated relationship to the numerical PWM goal.

## Completed source/history followup

`reported`: the pairs already occur in the initial ILI97701A EVT addition,
[commit20b82efff00c0781ff775a1a00679c038682b974](https://github.com/moto-sm8850/android_kernel_motorola_sm8850-devicetrees/commit/20b82efff00c0781ff775a1a00679c038682b974),
author-date2025-12-25. Its message says “add DC on/off code for low light effect”.
The pinned [v2 source, OFF lines74–84 and ON lines105–115](https://github.com/moto-sm8850/android_kernel_motorola_sm8850-devicetrees/blob/20b82efff00c0781ff775a1a00679c038682b974/display/dsi-panel-mot-boe-ili97701A-682-1440x3168-dsc-cmd-common_v2.dtsi#L74-L115)
contains the same `0E/11` versus `8E/11` pairs. Parent independently checked the
commit and source. This is a community mirror with Motorola-origin metadata, not
an authenticated OEM release. The commit's named threshold16000 belongs to APL,
not these pairs or PWM frequency.

The bounded v2/v3/v4 history and exact public searches yielded no encoding for the
high bit, comparator, EM pulse count or period. This is a completed search with a
negative result, not proof that documentation or a high-frequency hardware mode
does not exist. Historical low-light/DC association strengthens the selector
hypothesis, not a frequency-register interpretation.

## State and blocker

Target restored to auto brightness/original refresh policy/timeout/screenOFF,
DC0/logger0/Enforcing, own probes/files removed. No reboot, kernel/module/DTBO/image
write or permanent PWM setting. Camera remains intentionally prepared; original
camera restoration is still tracked in `artifacts/pacman_exact_session_20261106.json`.

Night stages1–4 are complete; R3 remains **blocked, not complete**. The finite series
has consumed its four one-shot candidates, and the bounded offline followup found
no justified next frequency-setting value. No experiment or research job is running.
New custom combinations, low-byte shifts or register sweeps are not covered by this
completed series. The existing DC-like effect does not meet the requested outcome.

Missing evidence: a target-relevant EM count/period field and timebase, or a known
higher-frequency sequence for this panel/revision with evidence linking it to the
optical waveform. A new documented sequence would permit a precise next proposal;
a separately scoped causal experiment could instead test a specific remaining
hypothesis, but cannot be presented as an established >=2000Hz setting. Availability
of the hardware mode itself remains `unknown`, not disproved.

No useful high-frequency profile is ready to install. Android persistence/UI must
not package the observed DC-like result as a solved PWM control. R1/R2 stay verified;
the final objective is not complete.
