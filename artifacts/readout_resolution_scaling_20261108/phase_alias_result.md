# Stock 720p → 4K → 720p: temporal phase alias (offline)

`confirmed-on-target` applies to the archived **stock screen video**, not to
physical PWM frequency. No new camera, ADB or DSI operation. [The original
capture](../pacman_readout_capture_20261106.json) used DBV3600, DC OFF,
requested120 and Pacman 100 µs/ISO6400 at nominal 30 fps. The earlier
[spatial resolution control](result.md) already showed that the fine pattern
occupies about three times as many encoded rows in 4K as in 720p; this follow-up
tests a different observable, its **frame-to-frame phase**.

[Reproducer](phase_alias.py) reuses the exact decoded Y-plane ROIs and three
overlapping 75-frame windows from the [spatial analysis](analysis.json). The
camera-image frequencies are fixed at `h×720/(V×93.43)` cycles per encoded
row, `h=1,2,3`, `V=720/2160`. Per-frame row profiles are detrended with degree-2
Legendre polynomials, Hann-weighted, and projected onto those frequencies.
The unwrapped phase is fitted against **frame index / nominal 30 fps**. Encoded
PTS deviate from that grid by at most 0.67 µs after `ffprobe` decimal formatting;
the underlying encoded time-base steps are exactly 3000 ticks at 1/90000 s,
not measured sensor jitter or verified exposure timestamps.
[All nine window results](phase_alias.json)
retain image-component amplitude and single-slope coherence.

| Saved stage | Fine alias in frames90–164 | Fine alias in frames115–189 | Fine alias in frames140–214 | Central-window coherence |
|---|---:|---:|---:|---:|
| A1, 720p | 1.110 | **1.124** | 1.188 | 0.9971 |
| B, 4K | 1.223 | **1.204** | 1.195 | 0.9981 |
| A2, 720p | 1.381 | **1.394** | 1.375 | 0.9957 |

These values are **cycles per nominal camera second of a sampled image-phase
alias**, not OLED PWM Hz. The second/third spatial image-components track
approximately 2×/3× the same per-stage drift; that does not establish physical
emission harmonics. The difference between the two *same-resolution* 720p
stages (central 1.124→1.394) exceeds either adjacent cross-resolution difference
(1.124→1.204, 1.204→1.394). Thus a difference in the 4K stage cannot be
identified as the effect of changing the recording resolution: elapsed time,
camera processing and panel state remain confounded. Three within-clip windows
overlap and are not independent trials. A1 late 1.188 and B late 1.195 are
close, but neither equality nor physical source follows from this comparison.

No independent camera row time or panel fundamental is obtained. The nominal
30-fps sampling retains integer-30-Hz aliases; the encoded PTS do not resolve
them. The on-screen pattern can still involve ISP, scanning or physical
low-frequency emission. `physical_pwm_hz` remains null. R3 ≥2000 Hz is open;
A9-only q93 RMS ratio 0.2264067 remains the best *intermediate panel* baseline,
not an optical frequency measurement. A0D1C1 has not been approved or sent.

Verification: source→JSON reproduced byte-for-byte; normal and `python -O`
reject overwriting the output without changing its bytes/mtime; ten nearest
optical-spectrum unit tests and scoped syntax/link checks pass. Independent
review decoded native Y without our decoder and recalculated all 27 phasor
components using QR detrending and direct sin/cos sums (maximum phase-slope
discrepancy 6.22×10⁻¹⁵ cycles/nominal s), with no proven defect or overclaim.
