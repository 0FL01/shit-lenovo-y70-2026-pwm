# Moving broad band across screen width — offline control

`confirmed-on-target` means **an image component in the saved recording**;
the physical source and PWM Hz remain `unknown`. This tests a different
question from the earlier [fixed 3:1 broad/fine phase check](../selector_broad_phase_20261108/result.md):
does the *moving* broad band appear coherently across separated horizontal
parts of the photographed screen, or only in one local UI region?

The [reproducer](analyze.py) decodes exactly the previously selected five
75-frame windows from the unchanged
[selector-split MP4](../optical/pacman_dsi_selector_split_20261107.mp4).
It uses the original limited-range camera Y plane, rows 190–689 and five
60-pixel-wide x strips `210–269`, `350–409`, **reference `540–599`**,
`640–699` and off-screen `900–959`. The reference strip's **all 375 row
profiles match the saved original NPZ exactly**; no replacement of the
approved stock/A9/stock/9D/stock windows. [Numeric result](analysis.json)
contains both unmodified profiles (`raw`) and a separate diagnostic which
subtracts each stage's stationary row profile (`moving_only`). The latter
measures *moving* broad structure only, never total panel modulation or the
previous A9 q93 RMS. Per-frame Legendre detrend degrees 1/2/3 and Hann spatial
Fourier phasors are evaluated at the two fixed frequencies `1/(3×93.43)`
and `1/256` cycles/output row. The statistic is the magnitude of the mean
unit-phase difference from the reference strip; it is not a PWM measurement.

| Stage, moving-only, degree 2, q=1/(3×93.43) | Reference broad amplitude, Y codes | Off-screen amplitude, Y codes | Left / mid / right phase coherence |
|---|---:|---:|---:|
| stock | 0.969 | 0.043 | 0.951 / 0.890 / 0.947 |
| A9-only | 1.328 | 0.050 | 0.998 / 0.998 / 0.997 |
| stock return | 0.685 | 0.034 | 0.850 / 0.862 / 0.779 |
| 9D-only | 0.861 | 0.035 | 0.911 / 0.874 / 0.934 |
| final stock | 0.817 | 0.035 | 0.940 / 0.857 / 0.897 |

Across all five windows, three screen strips and degree 1/2/3, moving-only
phase coherence ranges **0.736–0.998 / 0.779–0.998 / 0.885–0.999**;
reference/off-screen mean-amplitude ratios range **17.4–25.3 / 20.3–26.6 /
22.9–30.4**. The raw (stationary + moving) phase comparisons are much less
coherent (degree-2 screen median 0.559), consistent with static UI mixing into
the broad band. The separate `1/256` sensitivity result is retained in JSON.

This is evidence of a screen-localized, row-spanning **moving image pattern**
that persists under A9-only despite the separately proven fine-component
suppression. Off-screen has a much weaker Fourier amplitude, so its phase
coherence alone is not an equivalent positive control. A row-global camera/ISP
response to bright screen content, reflections, panel scan and OLED emission
remain competing explanations. Fewer than two broad cycles fit the 500-row
crop; subtracting the stationary profile is appropriate to this *dynamic*
question but would hide stationary PWM-like structure. **Neither the
fundamental frequency nor absence of a low-frequency envelope is established.**
No ≥2000 Hz claim follows. A9-only remains the best intermediate panel
baseline, q93 ratio 0.2264067, and the new
[A0D1C1 series](../dsi_coupled_9d_20261107/proposal.md) is still **NOT
AUTHORIZED / NOT RUN**. No phone, camera, DSI, settings or flash operations
were used here.
