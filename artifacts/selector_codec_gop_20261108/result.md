# Selector video HEVC-GOP control — offline only

**Hypothesis tested:** the moving broad stripe remaining under A9-only might be
an I-frame/GOP-locked decoding artifact, rather than a signal already present
in the camera frames. This is a test of *one codec signature*, not a way to
measure OLED PWM. No device action or new recording occurred.

The [reproducer](analyze.py) combines `ffprobe` frame types and the existing
2679×500 central-row profiles from the original
[selector recording](../optical/pacman_dsi_selector_split_20261107.mp4).
The encoded stream contains **112 I and 2567 P frames, no B frames**, with an
I frame every 24 frames. Video timestamps and archived profile timestamps
differ by a **constant 0.1025 s**, with <2 µs variation; this checks frame
index alignment, **not** sensor exposure timing. The exact five previously
selected 75-frame windows are stock/A9-only/stock/9D-only/stock. Each has three
interior I frames and 70 interior P frames; the first/last frames are omitted
because the test needs both adjacent frames.

For each window the script uses the same central ROI, subtracts the *stage
mean* row profile to examine the moving component, degree-2 Legendre spatial
detrend, Hann window and Fourier phasors at fixed broad `1/(3×93.43)` and fine
`1/93.43` cycles/output row. Its discontinuity metric in camera Y codes is
`|z[i] − (z[i−1]+z[i+1])/2|`. The phase rank compares the median at the true
I-frame position (`frame_index mod 24 = 0`) to all 24 possible GOP-position
labels on the **same decoded frames**; rank 1 is the largest median, not a
statistical significance threshold. Full numbers: [analysis.json](analysis.json).

| Stage | Broad median error I / P, Y | Broad I rank /24 | Fine I rank /24 |
|---|---:|---:|---:|
| stock | 0.06483 / 0.02855 | 1 | 1 |
| A9-only | 0.02005 / 0.02775 | 20 | 14 |
| stock return | 0.02852 / 0.03134 | 16 | 5 |
| 9D-only | 0.01731 / 0.03807 | 23 | 2 |
| final stock | 0.02804 / 0.04169 | 19 | 4 |

The specific hypothesis of a **reproducible broad-band jump at every I-frame**
is not supported across these five windows: only the first stock stage has
rank 1; the A9-only broad pattern remains despite a rank of 20. Fine-band
rank and error can differ, so this does **not** establish an artifact-free
video, eliminate motion-compensated compression/ISP effects in P frames, or
show that any stripe is OLED emission. The observed ~1.3 cycles/s sampled
optical alias is close to the GOP cadence `30/24=1.25 Hz`, so a coincidence
of phase over a short window cannot by itself establish causality. Subtracting
the stage mean also discards stationary image structure; this check does not
replace the original A9-only **q93 total RMS ratio 0.2264067**.

**Outcome:** one codec-only hypothesis narrowed; physical PWM Hz, an actual
low-frequency envelope, and ≥2000 Hz remain `unknown`. A9-only remains the
best intermediate panel baseline, not a verified high-PWM profile. The new
[A0D1C1 trial](../dsi_coupled_9d_20261107/proposal.md) remains NOT AUTHORIZED /
NOT RUN; HORIZON is not its operation-specific consent. No DSI, camera, ADB,
settings, reboot or flash action was performed.
