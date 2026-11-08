# Selector-series broad/fine phase: bounded offline check

`confirmed-on-target` only for the **saved optical recording**, not for panel
emission or physical Hz. Reused the completed
[stock→A9-only→stock→9D-only→stock series](../dsi_selector_split_20261107/result.md)
without another DSI command, capture, register read or phone action. Source:
`/home/stfu/.cache/opencode-tmp/opencode/dsi-selector-split-20261107/analysis-profiles-spatial-v2.npz`
(2679×500 camera Y profiles, ROI `[540,190,60,500]`, five archived 75-frame
windows). [Reproducer](analyze.py) and [machine result](analysis.json) keep the
original fixed fine spatial frequency `q=1/93.43` output rows, degree-2
Legendre/Hann processing and validate all five historical q93 RMS values.

## Falsifiable hypothesis and observation

`hypothesis`: the wide bands are the fundamental of the fine train, whose
frequency is its third spatial harmonic. Compare the *same-frame* unit-phase
relation `fine_phase − 3×broad_phase` at `q_broad=q_fine/3` against two
preselected neighboring broad frequencies `q_fine/3±0.001` cycles/output row.
Resultant length `|mean(exp(i×phase_relation))|` lies in `[0,1]`; it is **not**
an absolute PWM Hz, physical modulation depth or significance test. Broad has
only ~1.78 cycles across the 500-row ROI at the proposed frequency.

| Stage (degree-2 detrend) | Fine mean Fourier amplitude, Y codes | Broad mean amplitude at fine/3, Y codes | Relation at `q−.001 / q / q+.001` |
|---|---:|---:|---:|
| stock | 4.420 | 0.928 | 0.661 / 0.743 / 0.577 |
| A9-only | 0.697 | 1.307 | 0.422 / 0.366 / 0.714 |
| stock after A9 | 4.191 | 0.676 | 0.409 / 0.462 / 0.607 |
| 9D-only | 4.317 | 0.832 | 0.525 / 0.547 / 0.655 |
| final stock | 4.299 | 0.798 | 0.425 / 0.558 / 0.631 |

At `fine/3` the five resultants under detrend degrees **1/2/3** are,
respectively, `0.564/0.743/0.474` (first stock),
`0.654/0.366/0.332` (A9-only), `0.501/0.462/0.378` (stock return),
`0.477/0.547/0.445` (9D-only), `0.447/0.558/0.457` (final stock).
The proposed fixed 3:1 relation has **no stable, specific preference** over
nearby frequencies across the control/return windows or detrend choices.
The weak A9-only fine phasor makes its phase especially unreliable. These
data therefore do **not establish** the broad stripe as an OLED fundamental;
they do **not exclude** a physical low-frequency envelope either. Spatial
background, camera/scene motion and sensor mapping remain confounders.

The A9-only q93 RMS ratio **0.2264067** remains the best intermediate panel
baseline; the normalized *mean* Fourier amplitudes above are different
statistics from that RMS. Neither is a measurement of physical PWM frequency.
With the present saved footage and unknown camera row-time/harmonic order,
there is still no qualification of ≥2000 Hz. Next causal panel experiment is
the separately authorized [A0D1C1 proposal](../dsi_coupled_9d_20261107/proposal.md),
not another replay of the completed selector trial. It is **NOT AUTHORIZED /
NOT RUN**; no flash or persistent display profile is part of this offline work.
