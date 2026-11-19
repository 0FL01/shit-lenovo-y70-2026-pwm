# Round 11 (offline): Chop Frequency/Depth Estimates from Existing DNGs (`2026-11-19`)

## 1. Purpose and Method

No device work: re-analysis of R9/R10 DNGs to constrain the residual modulation of the cumulative-landed DC state before spending on-device rounds on compensation tuning.

- **(A) sinc consistency:** if the DC-landed residual is a periodic modulation of frequency `f`, the block-dip fraction `frac_lt_065` should fall with `|sinc(f·T_exp)|`. The six R10 v3 sweep points (2 frames each, `125–12500 µs`, BL verified per pair) were fit against candidate frequencies with a linear `0.42·|sinc|` model.
- **(B) band geometry:** green row-profile (both CFA sites interleaved) over the analyzer ROI strip (`rows 90–270`, `cols 1860–2020`), 21-row Hann smoothing, dark-run detection at `0.75×median`. Absolute row→time uses the labeled assumption `row_pitch ≈ frameDuration/rows = 33.33 ms / 2448 ≈ 13.6 µs/row`.
- Scripts: [r11_band_v2.py](r11_band_v2.py) (metrics JSON: [r11_band_v2.json](r11_band_v2.json)); the first full-height variant ([r11_band_analysis.py](r11_band_analysis.py), [r11_band_metrics.json](r11_band_metrics.json)) was too noisy at single-row resolution (100+ noise runs per frame) and is kept as the negative method note.

## 2. Results

1. **sinc plateau `480–720 Hz` (weakly constrained):** RMSE of `lt065` vs `0.42·|sinc(f·T)|` over the six exposure points: `480 Hz: 0.117` (best), `600: 0.161`, `640: 0.185`, `720: 0.179`, higher candidates rise to `0.28–0.48`. With 2 frames per point and a crude linear model this does **not** establish a frequency; it excludes nothing in `360–960 Hz` and argues against `≥1200 Hz` **under the periodic-chop assumption only**.
2. **Dark-event geometry (frame labels corrected: `IMG_20260502_144131564` is the dark `625 µs` frame, `0.3837 DN`):** on dark frames the smoothed ROI profile contains **single wide dark runs of `≈463 µs` and `≈735 µs` duration** (depth to `0.13–0.50×median`), one per ROI window (ROI time extent `≈2.45 ms`); the bright frames of the same pairs show at most one shallower run. The PWM baseline frame shows its known single `≈844 µs` refresh notch. Interpretation: the DC-landed state emits **deep dark events of ~0.5–0.8 ms**, caught by roughly half of short-exposure frames — compatible with a low-duty event train on a ≳1.5 ms recurrence scale, and with the clean look of `12.5 ms` frames (a single event contributes only ~5% to a `12.5 ms` row integral, below the `0.65` block threshold).
3. **The events are DBV-dependent (from R9/R10 artifacts, no new data):** at `625 µs` in the cumulative-landed state the worst block minima deepen as DBV falls — `2048: binned_min +0.01…+0.40` (no dark events), `1024: −0.33…−0.43` (shallow), `512: −1.06…−1.48`, `460: −0.97…−5.8` (deep, frequent). The chop is the DC dimming acting at low brightness; the compensation-parameter space (`53:95`, PAM block, `53:A2`, `51/52`) is the tuning target for pushing the event-free regime down to the owner's brightness range.

## 3. Honest Bounds

- Camera data alone cannot replace a DC-coupled photodiode: the `480–720 Hz` plateau and the `0.5–0.8 ms` event durations are consistent-but-coarse; sporadic (non-periodic) events fit the data as well as a periodic chop.
- `row_pitch = 13.6 µs/row` is an assumption (readout ≈ frame interval); band durations scale linearly with it.
- All statements concern the cumulative-landed replica state at `panelDC = 0`; no claim about the stock `panelDC = 1` path beyond the R7/R9 signature resemblance.

## 4. Next

- **R12:** at readback DBV 460 (cumulative-landed), iterate `53:95` through interpolated values between `dc-off (00 a0)` and `dc-on (44 50)` plus overshoot, 3–4 frames at `625 µs` per point, band metrics offline: does any value kill the dark events at matched brightness?
- **R13+:** same for the PAM block (25/50/75/100 % interpolation), `53:A2` tail, `51/52`; then entry-path variants; event-rate statistics at the winner; full A-B-A + snapshot restore; recipe consolidation.
