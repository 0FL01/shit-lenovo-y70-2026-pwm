# Broad moving image band across stock exposure sweep — offline

`confirmed-on-target` applies **only to the saved camera image**; the physical
source and PWM Hz remain `unknown`. This asks whether the broad *moving* band
remains screen-localized and coherent across x at the 1428.571 µs exposure
minimum, when the [fine image component](envelope_check.md) is strongly
attenuated. The previous [selector x-strip test](../../selector_broad_x_20261108/result.md)
used a different recording at one exposure; neither result measures OLED Hz.

[Reproducer](x_strip_exposure.py) uses the unchanged
[stock MP4](../../optical/pacman_exposure_notch_supported_20261107.mp4) and
[original window inventory](analysis.json) with the saved private decoded
profiles for exact center-ROI validation. It selects six original 75-frame
windows (inclusive indices 643–717, 1864–1938, 2721–2795, 3700–3774,
4926–5000, 5657–5731), no new recording. The original limited-range Y
plane is sampled at y=190–689 in five 60-pixel x strips: screen left210–269,
mid350–409, center540–599, right640–699, offscreen900–959.

The [numeric output](x_strip_exposure.json) stores metrics for `raw` row
profiles (without stage-mean subtraction) and a *separate* `moving_only`
diagnostic that subtracts each stage's mean row profile. Both modes use
Legendre detrend degrees1/2/3 and Hann Fourier at fixed broad frequencies
q=`1/(3×93.43)` and `1/256` cycles/output row;
unit-phase resultant relative to the center across 75 frames. The table
uses **moving_only**, degree2, first q. `A/(meanY−16)` is a camera-code
normalization, not linear optical modulation or an OLED duty measurement.

| Exposure µs | Center amplitude A, camera Y codes | A/(meanY−16) | Center/offscreen amplitude | Left / mid / right phase resultant |
|---:|---:|---:|---:|---|
| 100 initial | 0.270 | 0.0564 | 8.15 | 0.960 / 0.981 / 0.929 |
| 500 | 0.853 | 0.0367 | 18.77 | 0.969 / 0.940 / 0.759 |
| 1000 | 1.585 | 0.0368 | 31.19 | 0.995 / 0.994 / 0.987 |
| 1428.571 | 1.589 | 0.0279 | 33.53 | 0.999 / 0.998 / 0.999 |
| 2000 | 1.724 | 0.0236 | 32.90 | 0.998 / 0.997 / 0.998 |
| 100 final | 0.349 | 0.0719 | 8.53 | 0.972 / 0.980 / 0.974 |

The degree2 center camera-code ratio at1428.571 µs relative to the mean of
the two 100-µs controls is **0.4352** for this *moving-only broad Fourier
amplitude*. The previously reported fine **total RMS** camera-code ratio
was ~0.0328: different bands and different aggregations, not a calibrated
comparison of physical modulation depths. In the raw degree2 profiles at
1428.571 µs, mid/center phase resultant is only ~0.098; subtraction
intentionally removes stationary UI/stripe structure and reveals the moving
image pattern, not the whole emitted signal. With degrees1/2/3 the moving-only
notch/control ratios are 0.3435/0.4352/0.4900 at the first q, and
0.3368/0.4046/0.4579 at `1/256`; the result depends on detrending and
frequency choice.

**Bounded finding:** at the fine-notch exposure, a broad moving *camera-image*
pattern still spans separated screen strips, with much smaller Fourier
amplitude in this offscreen strip. This does not establish a physical
low-frequency OLED envelope, its absence, a fundamental frequency, or
≥2000 Hz. Fewer than two broad cycles fit the crop; time-varying camera/ISP
row processing, reflection, changing UI, exposure nonlinearity and panel
scanning remain competing explanations. Offscreen darkness makes its phase
resultant unreliable; even high cross-screen coherence alone cannot identify
the source. This does not replace the saved A9-only q93 panel baseline
0.2264067. The next [A0D1C1 panel trial](../../dsi_coupled_9d_20261107/proposal.md)
is **NOT AUTHORIZED / NOT RUN**; its stock return and emergency ordinary
reboot need separate exact consent. No devices, DSI, settings or flash were
used in this analysis.

Validation: the saved 72-record JSON is reproduced byte-for-byte by the
reproducer; normal and `python -O` invocations refuse to overwrite an existing
output without changing its bytes/mtime. An independent review decoded the
original Y frames, matched all 225,000 center-profile values, and recomputed
all 720 numeric strip metrics with a separate QR/Fourier implementation
(maximum differences 3.11×10⁻¹⁵ Y codes and 1.51×10⁻¹⁴ coherence). The initial
two-q mixing error was fixed **before** this saved result and review.
