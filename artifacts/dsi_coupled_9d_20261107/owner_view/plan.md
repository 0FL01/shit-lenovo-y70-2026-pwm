# One session-only A0D1C1 manual view

**CURRENT 2026-11-08 08:12:31 UTC: stock return verified.** Following the
manual view, the owner requested stock for live inspection. The single
[return report](return/run.json) verifies 75 factory packets, A9/9D=`0E/0E`,
DBV=`0E10`, `stock_return_verified=true`, `target_restored=true`,
`owner_view_active=false`, ESD reg_read and successful cleanup. At runner
completion original manual52/refresh120/timeout1800000/native DBV3584 were
restored; one later read-only native DBV was3356 despite Android52 and panel
power0/DC0, cause unknown. Do not overwrite settings while the owner compares
stock live. The manual-application/return instructions below are **history**,
not permission for a second application. Neither flash nor reboot occurred;
there is no established physical PWM frequency or comfort verdict.
[Offline A001 video comparison](optical_compare.md) uses stock DBV3584 versus
candidate DBV3600 and finds overlapping fine image amplitudes, not an
equal-condition proof. Preserve both run reports, authorizations, videos and
this plan for migration; reidentify devices before any future operation.

The owner specifically requested applying A0D1C1 and pausing for manual viewing
**without automatic stock return**. This amends the earlier three-stage proposal
for this one manual application; it does not authorize another DSI profile,
flash, repeat or persistence after reboot. The exact candidate/stock hashes and
ordinary emergency reboot if the command queue is uncertain remain unchanged.

`python3 06-tools/run_dsi_mode_trial.py TARGET_TRANSPORT 0 --coupled-9d-view`
checks identity/root/module, initial stock state, sends stock then the same
A0D1C1 candidate once, replays DBV3600, redraws and checks exact A9/9D/DBV
readbacks, native trace, ESD and cleanup. It leaves A0D1C1 and the temporary
manual52/requested120/DBV3600/10-minute timeout policy active for the owner.
No camera recording occurs in this manual view; camera transport `0` is an
unused placeholder. The output is `owner_view/run.json` with
`owner_view_active=true`, **not** `target_restored=true` or measured PWM Hz.
Do not assume this profile survives screen-off, display reset or reboot.

On the owner's stock-return instruction, first re-identify the target and run:
`python3 06-tools/run_dsi_mode_trial.py TARGET_TRANSPORT 0 --coupled-9d-return`.
It refuses an uncertain queue or missing active-view proof, sends the full
stock program and restores the captured Android policy and native DBV;
`owner_view/return/run.json` is its separate return record. Ordinary reboot
into stock initialization is the approved emergency route if queue/completion
becomes uncertain; check target identity, root and Enforcing afterward.

For a portable handoff preserve this plan, both authorization files, the
actual `owner_view/run.json` and approved private logs **without serials or
camera identifiers in reports**. Keep the phone awake and unchanged while
visually comparing; do not change brightness, DC mode, refresh, suspend or
unplug it and presume retention. Stop inspection at discomfort, request stock
return or use ordinary reboot if a safe command return is unavailable. A9-only
remains the best earlier optical baseline, not a physical-Hz calibration.

## Historical 2026-11-08 handoff (candidate was active; not stock then)

The single approved manual run finished at 07:57:08 UTC: `owner_view/run.json`
records two verified 75-packet stages, stock A9/9D `0E/0E`, candidate `0E/8E`,
DBV `0E10`, `owner_view_active=true`, `stock_return_verified=false`,
`pending_bytes_may_exist=false`, `esd_restored=true`, and no cleanup errors.
There is **no** `owner_view/return/run.json`. The user requested a pause without
stock return. Do not run the application again or presume that the panel
retains it after sleep/reboot; the manual return above is for a later owner
instruction, and an uncertain queue uses ordinary reboot rather than another
batch. At handoff DBV is3600 and temporary Android timeout600000ms; the
captured before-values in `run.json` include native DBV3584 and timeout1800000ms.

The replacement camera is Nothing A001/Galaga, not the historical G54:
Open Camera1.56.2 Camera2 rear H264 1280×720/30fps, audio OFF, exposure100000ns,
ISO6400, AE/AF/OIS/EIS OFF, manual focus2.03874850 and crop `0 0 4080 3072`.
The self-recorded `../../optical/a001_a0d1c1_manual_20261108.mp4` is 13,847,707B,
11.933100s, no audio, with the Lenovo screen visible inside ROI
`[540,190,60,500]` (native Y≈33 vs offscreen≈21, no saturation). The earlier
A001 stock test is only in approved private cache at DBV3584, NOT an equivalent
DBV3600 optical control. No physical PWM Hz or comfort result follows.
Before using any saved transport ID after migrating, reidentify both devices,
check target root/Enforcing/actual panel state, and verify camera settings anew.
Keep original authorizations, this plan, source binaries, `owner_view/run.json`,
and the candidate video; approved private logs/video may need separate secure
copy, with no serial/identifier publication. The return command above must
not be silently skipped or mistaken for completed restoration.
