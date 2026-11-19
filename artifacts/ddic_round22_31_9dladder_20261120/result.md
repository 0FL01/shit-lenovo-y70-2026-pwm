# Rounds 22–31: the `24:9D` drive ladder on the re-based rig (`2026-11-19/20`, overnight)

> **Rig note (mandatory):** the owner re-assembled the bench before this session; the white field no longer covers the day-campaign ROI (raw `y90–270, x1860–2020`). This campaign is **internally re-based**: a new ROI `(b2 y500–590, x580–660)` inside tonight's white core, a new reference flat (`IMG_20260502_170254392.DNG`, stock PWM at DBV 6879, 624 µs), and a new PWM@512 baseline. **All numeric comparisons in this report are internal to tonight's rig; cross-references to R9–R21 are qualitative only.** All 172 analyzed DNG frames carry the ISO 6400 tag; exposures are 152 × 624 µs, 19 × 156 µs and one 625 µs frame (`IMG_20260502_170258744.DNG`, the second flat frame, not the flat itself) — the nominal 1/1600 step reads 624 µs tonight (dumpsys 624000 ns) where the day campaign recorded 625 µs.

## 1. Purpose and method

The owner restated the goal: **(A) full PWM-off** (no residual modulation at evening brightness) or **(B) push the PWM carrier to ≥2 kHz** — the user is PWM-sensitive. This campaign mapped the previously unexplored `24:9D` value space (R16/R19 had probed only `0x0e` and `0x8e`), looked for a quiet low-level state, and made a first probe of the PWM-frequency branch.

Method: guarded `unshare -m` debugfs transactions as before. Each phase = full `dc-off` snapshot restore (`r9_ret.cmd`) → apply → frames; the restore is gated by comparing three readbacks against the stock values (`23:A9=0x0e`, `24:9D=0x0e`, `23:80=0x50`), the apply by `PHASE_DONE fail=0` and at least three `W_OK` lines (not a per-write readback of every field); `esd_check_mode` returns to `reg_read` in every transaction's `trap EXIT`. `55` apply logs with `fail=0` and `ESD_RESTORED reg_read` are preserved. The steady-burst series **continue** their phase entries (they are not independent restores). `61` analysis groups cover `172` frames, of which `170` produced metrics and `2` were too dark for the flat normalization and are recorded as errors (`r28_8e_g32/0`, `r28_92_g16/1`).

## 2. The `24:9D` ladder — requested vs. read-back codes (white, sysfs 512, 624 µs)

**The register masks its writable space (confirmed-on-target).** Requested codes are not all stored: `0x4e/0x5e/0x6e/0x7e` read back as `0x0e/0x1e/0x2e/0x3e` (requested bit6 is dropped), and `0xce` reads back as `0x8e`, `0xee` as `0xae`. The optical results of such phases are therefore measurements of the *read-back* codes (`r24_9dce` is another `0x8e` entry; `r24_9dee` is another `0xae` entry).

Levels by **read-back** code (means over the phase frames, `summary_round22_31.json`):

| read `24:9D` | requested codes probed | level, DN | lt065 | character |
|---|---|---|---|---|
| `0x0e, 0x1e, 0x2e, 0x3e` | `0x0e…0x7e` (low nibble fixed `e`) | 0.375–0.444 | 0.377–0.415 | one flat low plateau; heavy chop |
| `0x80, 0x82, 0x83, 0x84, 0x85, 0x88, 0x8a, 0x8c, 0x8e` | same | 0.30–1.55 | 0.221–0.436 | bit7=1 low family, all choppy (recipe `0x8e` = 1.55 / 0.246) |
| `0x81` | `0x81` | 0.282 | 0.467 | low, choppy (listed separately) |
| `0x8f` | `0x8f` | 22.57 | 0.043 | least-banded of the ~22 DN group |
| `0x90, 0x92, 0x94, 0x98` | same | 21.89–23.96 | 0.000–0.076 | the low quiet family |
| `0x91` | `0x91` | 20.89 | 0.132 | quieter level, banded |
| `0x9c` | `0x9c` | 268.60 | 0.000 | bright, quiet |
| `0x9e` | `0x9e` | 266.11 (rep) / 269.59 (r24) | 0.000 | bright, quiet |
| `0xa0` | `0xa0` | 275.83 | 0.000 | bright, quiet |
| `0xae` | `0xae, 0xee` | 398.95–405.05 | 0.000 | brightest, quiet |

Observations (confirmed-on-target, bounded to the probed codes and the fresh-entry path used):

1. **Between the low plateau and the recipe level there are only the bit7=1 low combos** (`0x80…0x8e`, 0.30–1.55 DN, all banded). No tested code in `0x00…0x8e` produces a quiet low level.
2. **The first clearly quieter group sits at ~21.9–24.0 DN** (`0x8f, 0x90, 0x92, 0x94, 0x98`; individual codes differ in banding). Above it, `0x9c/0x9e/0xa0/0xae` read 3.7–13.6 × the stock maximum-brightness reference of tonight's rig (100.56 DN). These are **camera-signal ratios, not calibrated luminance and not proof of electrical overdrive**; the long-term safety of sustained emission above the stock reference is unknown.
3. The single-bit reading of the ladder is value-dependent, not universal: adding bit0 raises `0x8e → 0x8f` (1.55 → 22.6) but lowers `0x90 → 0x91` (23.7 → 20.9) and changes `0x80 → 0x81` (0.57 → 0.28); `0x8c → 0x9c` jumps to 268.6. The report deliberately describes measured steps per code, not bit semantics.

## 3. Residual banding vs. drive level

Row-direction profiles (normalized per frame, flat-uncorrected row minima — "rowmin"; the summary's binned metric for the five banded `0x92` frames is `binned_min = 0.371–0.454`):

- **`0x8e` (recipe level, ~1.5 DN, 4-frame reference phase):** blocks fall to the camera-black/noise floor (`binned_min ≈ −0.84` after black subtraction — a dip to the black level, not a proven zero emission); lt065 0.246, bimodal across frames.
- **`0x92` (~22 DN, 8-frame steady burst at 624 µs):** 5 of 8 frames carry a wide band dipping to ~0.41–0.44 of the mean; the other 3 frames are clean (rowmin ≥0.89).
- **`0x9e` (~268 DN, 8-frame steady burst at 624 µs):** 4 of 8 frames carry a shallow band dipping to ~0.71–0.72 of the mean; the clean frames read rowmin ≥0.95. In a 6-frame steady burst at 156 µs no pronounced band was detected (2D peak amplitudes ≤ ~0.016). **This does not establish the carrier frequency or the absence of modulation**: a ~6.4 kHz periodicity integrates to one period at 156 µs and four at 624 µs and could evade both exposures; the frequency, the existence of a carrier, and true modulation-freedom are **not established** by these camera data.
- **`0x90` (~23 DN, 4-frame steady burst at 156 µs):** 1 of 4 frames shows a deep dip (rowmin 0.02), 3 frames clean — rare deep dips on a code whose 2-frame phase read lt065 0.000.

On the three probed levels the band depth decreased as the level rose (black-floor → ~57 % → ~28 % of the mean); monotonicity across the whole ladder is **not** established (three levels sampled; `0x90` shows a different dip pattern at another exposure). Together with the day rounds (six compensation knobs neutral, R12–R17) and tonight's dimming probes (§4): **on the tested codes and entry paths no quiet evening-level state was found.**

## 4. Dimming attempts on the quiet states (negative results, bounded)

- **sysfs BL 256/512/1024 with `0x9e`:** level 262.7–266.1 DN — no response at the three low set-points. At sysfs **3600/6873 the level drops to 88.2/96.3 DN** with a mild residual (lt065 0.007–0.010). The phase readbacks were taken **before** the BL change, so the mechanism (driver re-derivation) is a hypothesis; the drop itself is measured.
- **`23:80 = 0x50`:** 264.4 vs 266.1 at `0x9e`; 23.3 vs 22.9 at `0x8f` — within the banding variation.
- **`23:85 = 0x14`, `53:95 = 0x1188`, `4F:81 = 0x00` and `0xff`** (each a 2-frame pair on `0x92`): `8514` → 22.04/0.069, `951188` → 23.48/0.000, `4f8100` → 24.03/0.000, `4f81ff` → 20.83/0.130 against the short `0x92` base 23.96/0.000. The pairs show no reproducible dimming direction; the `4f81ff` dip is a single 2-frame observation, insufficient for either a real effect or a noise verdict. These writes have `W_OK` logs but **no readback of the changed fields themselves**.
- **Gray content:** `0x92` on `#404040` → 0.72 DN lt065 0.373; `0x8e` on `#404040/#202020` → 0.18/0.08 DN lt065 0.455/0.472; `0x92` on `#202020/#101010` → 0.23/0.11; `0x9e` on `#101010` → 0.69 lt065 0.372. Every probed gray combination lands at a content-scaled level with heavy banding — the quiet white-only character does not survive content dimming on the pairs tested.

**Net: none of the tested actions produced a reproducible evening level without bands.**

## 5. The PWM-frequency branch (goal B): first probe

In the **PWM state** (`23:A9=0x0e`), the `r30_pwm9e` phase (`24:9D=0x9e`, `C1 = 00 02 be` unchanged): the mean signal rose from 1.54 to 40.9 DN and the strong row-band component at `k=(2,0)` strengthened from 0.750 (stock PWM@512 baseline) to 0.875; `lt065` 0.512. **No transition to a different resolvable signature was observed.** The qualitative similarity of the band shape to the stock wave ("720 Hz-class", per the day rounds' estimate) is not a new frequency measurement: FFT-bin coincidence does not establish carrier equality, and `lt065` is a block fraction, not a duty cycle. **The probed `9D` codes were not shown to control the PWM carrier frequency; a frequency register, if one exists, was not localized** by this single probe plus the read-only page diff (§6).

## 6. Register cartography (R22)

Read-only page dumps, 16 addresses per guarded transaction, all `fail=0`: pages 23/24 in the DC state (page 24 covered 240/256 — the `0x00–0x0F` chunk was not taken in the DC state; the PWM-state dump covers all 256), pages 23/24 in the PWM state, pages 4F/51/52/53/63 in the DC state.

- Among the **496 comparable single-byte reads** of pages 23/24 (DC vs PWM), five addresses differ: the known core `23:A9` (`8e/0e`), `23:80` (`90/50`), `24:9D` (`8e/0e`), plus `23:52` and `24:52` (`03` in DC / `02` in PWM) — **addresses with an observed difference; their role is unknown**. The multi-byte `23:C1` also differs in its later bytes (first byte equal); the full list of changed multi-byte fields is not claimed.
- Pages 51/52/63 carry page-specific content (e.g. `52:81…84` = the known compensation block); low addresses (`0x00–0x4F`, incl. the ID byte `0x04=0xd2`) read identically across pages — **compatible with a common bank**, whose internal layout is not established.

## 7. Consequences for the owner

1. **Evening level (goal A): not achieved on the tested grid.** The recipe (`0x8e`) remains the chosen evening-level option for the owner's trial; several bit7=1 low combos (`0x8a` 1.37, `0x8c` 1.40 DN) read near it. No tested code produced a quiet evening-level state; the comfort verdict at this level remains with the owner's eye or a DC-coupled photodiode.
2. **A less-banded daytime group exists:** `0x8f/0x90/0x92/0x94/0x98` (~21.9–24 DN, ≈22 % of tonight's stock maximum reference) — sporadic bands instead of black-floor dips, with code-dependent patterns (§3). Left for the owner's perceptual trial; not enabled by default. The bright quiet codes (`0x9c/0x9e/0xa0/0xae`, camera-signal 2.6–4 × the stock maximum reference) are brightness-unusable for the evening and their sustained-emission safety is unknown — not candidates.
3. **Goal B (≥2 kHz):** tonight's single PWM-state probe showed no `9D` effect on the resolvable band signature; the carrier question stays open (unmapped pages, e.g. the `23:86–9D` config block or `24:9F/0xA0`, remain blind-probe candidates for a future round).
4. **Lifecycle of the new states (live session probes, outputs not part of the committed evidence):** `0x92` survived a sysfs sweep with registers intact at every step, was killed by screen off/on (stock re-init `0x0e/0x0e/0x50`) and healed by one re-apply; a `PUT 0` issued **without** a preceding `PUT 1` dispatched nothing (no state transition) — this does not contradict R21's defect, which was demonstrated on a real transition.

## 8. Verification and state

- Gates as described in §1; the two too-dark frames are reported as errors, not dropped; the summary (`summary_round22_31.json`) is the authoritative numeric source for this report — the interactive session tables contained an indexing slip corrected by the ordered spec builder.
- **Device restoration (performed live after the campaign, outputs in the session record):** Lenovo returned to the owner's trial state (3-write recipe ON, readback `A9=0x8e/9D=0x8e/80=0x90`, `C1=00 00 10`, sysfs 512, slider 20, launcher; `white.html` and the temp cmdfiles removed; `esd_check_mode=reg_read` at rest); A001 returned to the OpenCamera baseline (screen timeout restored; tonight's bench captures pulled to the private evidence dir and removed from the device).
- Known scope limits: one rig, internally re-based (no numeric continuity with R9–R21); camera-band discrimination only — the carrier frequencies of the quiet codes and the perceptual depth both remain open instrumentally; rowmin is a flat-uncorrected row-profile minimum, distinct from the summary's `binned_min`.

Files: [gen_r2231_spec.py](gen_r2231_spec.py) (spec builder: 61 groups, 172 frames, ordered capture consumption), [r22_analyze.py](r22_analyze.py) (round-local analyzer: the campaign analyzer's functions with the re-based `b2_roi=(500,590,580,660)`, `target_k=(2,0)`, narrow slice `(610,620)`; per-frame error capture; **no existing analyzer code modified**), [spec_round22_31.json](spec_round22_31.json), [summary_round22_31.json](summary_round22_31.json). Private frames and session outputs: `legion-y70-lab/private-bench-evidence/r113-20261119/r22/` (not in Git).
