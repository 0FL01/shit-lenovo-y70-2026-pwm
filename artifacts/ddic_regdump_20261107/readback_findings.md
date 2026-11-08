# DDIC readback audit and stock-history tests — 2026-11-07 UTC

R1/R2 remain verified; R3 is not solved. No new synthetic panel sequence, image,
module or persistent PWM profile was applied in these tests.

## Handoff audit

- `confirmed-on-target`, saved records: four completed known-page runs contain
  9728 requested reads each, not a decoded 19-page register map. The unfinished
  `s5_census_dbv3584_120` has no raw data or completion record; it was not resumed.
- `confirmed-on-target`, fresh06:25 inspection: ESD mode was still
  `esd_sw_sim_success`, despite the handoff's cleanup claim. Stock page0 and
  `reg_read` were restored and read back: [recovery evidence](esd_recovery_audit.json).
- `reported`, pinned driver `fa008c43c070ff20faa33853649f5dfd4c427e99`:
  `msm/dsi/dsi_ctrl.c:1758–1806,1809–1962` distinguishes short responses from a
  long-read path copying the requested length and potentially resending a read.
  Zero tails in a40-byte request do not establish40 meaningful registers.
  `23:A9` read of two bytes is not automatically `A9/AA`; opcodes can have
  multi-byte payloads without address auto-increment. DCS GET brightness is52,
  not the brightness-write opcode51.
- Broad legacy readers remain unsuitable for unattended reuse: host timeout can
  outlive their cleanup, and `run_ddic_regdump.py` contains an ineffective
  keyguard assertion (`or True`). These historical files/results were not rewritten
  to pretend successful completion. The new narrow reader avoids those paths.

## Test1: unchanged stock DC0 →1 →0, DBV3584 / software120Hz

`confirmed-on-target`,06:34:01–06:34:45:
[capture](stock_latch.json), [analysis](stock_latch_analysis.json),
[preview comparison](../optical/ddic_stock_latch_20261107.png).

| Readback | Initial OFF | Native ON | Native OFF |
|---|---|---|---|
| `4F:81` | `06` | `10` | `10` |
| `23:A9`, `24:9D` | `0E`, `0E` | `8E`, `8E` | `0E`, `0E` |
| `23:80` | `50` | `90` | `50` |
| `53:95` | `00 A0` | `44 50` | `00 A0` |
| `00:52` | `0E 00` | `0E 00` | `0E 00` |
| Optical preview | fine + broad bands | broad band remains | fine + broad bands |

`4F:C1/C9/D1` stayed06, `D9` stayed10. `4F:88/8B` read00 despite confirmed
stock writes78. The latter fields are not established persistent-write mirrors;
their self-clearing/bank/command semantics remain `unknown`.
The full ON/OFF tables matched150 native payload/type/HS/order records. All45
short reads returned the requested1/2 bytes;94 page-selector callbacks returned0,
293 controller returns were nonnegative, probe misses0. Reading itself did not
visibly change the band class in the before/after snapshots.

## Test2: stock120 →30 →120 → native DC ON/OFF at120

`confirmed-on-target`,06:39:38–06:40:38:
[capture](stock_timing_history.json), [analysis](stock_timing_history_analysis.json),
[preview comparison](../optical/ddic_timing_history_20261107.png).

Readback `4F:81` followed **10 →06 →06 →10**. Software refresh was checked in
each state. The30Hz transition emitted the live `timing@4` sequence containing
`81 06`; the120Hz return emitted `timing@0`, which does not rewrite that field.
The final native DC cycle emitted `81 10` in both directions.
The30Hz request also passed through a native `timing@7` preamble, DSC PPS and
DBV writes; these are explicitly accounted for, not silently dropped.208 packets
match complete live timing/DC sets, plus one128-byte DSC PPS and three unchanged
brightness writes.60 short reads,125 page callbacks0,403 nonnegative controller
returns, zero probe misses; no captured DMA error.

At the same final120Hz/DC0/DBV3584, both `81=06` and `81=10` retain the fine
preview pattern. Per-frame autocorrelation of the same blank strip found
204–207px across both tests' OFF states;30Hz also retained it. These pixels are
**not Hz**. Fixed camera100µs/ISO6400/AE+AF OFF/focus9.11752701 and stabilization
OFF were checked. Three preview snapshots per state do not calibrate physical
frequency, duty, modulation depth, sensor timing or panel temperature.

## Consequences and current state

- `confirmed-on-target`: stock mode history can produce the reported06 readback;
  the field is readable and tracks a stock write, rather than always returning06.
- `hypothesis` rejected as an inference: `06` by itself proves six EM pulses.
  A literal count model predicting16/6 frequency scaling between these observed
  values is not supported by the preserved fine band spacing. Other indirect
  roles of this field are not excluded: whole stock transitions, not isolated
  field writes, were used.
- `unknown`: exact `4F:81` semantics, an EM count/period field, its timebase and
  a profile meeting>=2000Hz. Repeated `01 06` bytes are not a register definition.
- Both runs used `06-tools/check_ddic_stock_latch.py`: native15s timeout plus3s
  kill deadline, child mount namespace, page0/ESD EXIT cleanup and independent
  host-finally recovery. Final ESD was verified `reg_read`; own trace/files and
  MIPI logger were removed/disabled. This is not a guarantee against every
  uninterruptible kernel or host failure.
- Captured temporary policy was preserved: target awake, manual52/DBV3584,
  requested120Hz,30-minute timeout, stay-on7, DC0 and Enforcing. **This is not the
  original pre-investigation automatic policy** (auto, no refresh override,
  5-minute timeout, stay-on0), which remains due at session cleanup. Pacman is
  intentionally prepared/awake. Persistent KernelSU is unchanged.

The narrow source/history followup is complete:13 unique v2/v3/v4 mirror
commits and6 official v4-history commits did not supply the live30/24Hz4F
insertion or a field definition. The parent independently checked official
`f088523dfba85c95c15f43726fcf972c0c7a957a` v4 lines878–909 and1040–1071:
both timing sets contain11 packets and no page4F. The live30Hz set has30
packets. This is a concrete source gap, not proof that no documentation exists.
Detailed bounded source audit is cached in
`/home/stfu/.cache/opencode-tmp/opencode/ddic-4f-followup-20261107/FINDINGS.md`.

No invented4F value is justified by these readbacks. A separate
[two-variant causal split](../dsi_selector_split_20261107/proposal.md) is prepared
offline: only23:A9, then only24:9D, using each one's native ON value. It is
not approved or sent; prior operation-specific trial permissions are consumed.
This is the next exact-operation boundary, not proof of hardware impossibility
and not a solved PWM objective.
