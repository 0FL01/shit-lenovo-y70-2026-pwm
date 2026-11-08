# Bootloader state

- `confirmed-on-target`, 2026-11-06 07:37:09–07:37:24 UTC: one explicitly owner-approved `fastboot oem unlock` with the owner-supplied local key returned `Bootloader is unlocked!` and `OKAY` (host exit 0). Key value was never printed or submitted externally by the agent.
- `confirmed-on-target`, independent read at 07:38:02 UTC: `securestate=flashing_unlocked:SDP`, `product=avr`, `sku=XT2611-1`, `current-slot=b`, `is-userspace=no`. Final bootloader unlock is verified; do not repeat it.
- `confirmed-on-target`, 07:45 UTC after owner completed setup: authorized ADB, `sys.boot_completed=1`, `flash.locked=0`, `vbmeta.device_state=unlocked`, Verified Boot orange, same build/kernel/slot `_b`, ordinary shell UID 2000 and SELinux Enforcing. Earlier bounded ADB timeout was not boot failure.
- `unknown`: stock/custom recovery applicability/access, current-build restore originals and root. Unsupported `unlocked`/battery percentage getvars are not evidence; previous Android green/locked observations are historical.
- Owner accepts full wipe; user-data/on-phone backups are not a prerequisite. Unlock and future image/DSI experiments still require their exact operation plan and confirmation; no implicit AVB, critical-unlock, slot change or cross-flash authorization.
- Evidence and next steps: [2026-11-06 RECON and plan](unlock_pwm_recon_2026-11-06.md); unlock gate: `05-safety/gates.md`, G0U.
- Execution journal: [bootloader_worklog_2026-11-06.md](bootloader_worklog_2026-11-06.md), post-boot evidence: [post_unlock_observation_2026-11-06.json](post_unlock_observation_2026-11-06.json). **R1/T00 verified/done.** Root remains a separate required stage; subsequent device work is paused for owner-requested TWRP/OrangeFox research.
