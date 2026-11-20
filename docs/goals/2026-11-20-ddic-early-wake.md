# Goal: apply the `0x8e` panel profile during wake

- Status: active
- Source: owner-approved sequence: passive wake trace → observer LKM only if needed → vendor apply only if qualified.
- Last updated: 2026-11-20

## Frozen contract
- **R1 — characterize wake** (`verified`): native `0x11`, `0x29`, first positive DCS brightness and DC setter versus actual host traffic in [four full wakes and two verified AOD wakes](../../artifacts/ddic_wake_recon_20261120/result.md). Packet timing is not first light.
- **R2 — qualify an observer LKM only if passive tracing is insufficient** (`not_applicable` for R1): tracefs resolved the native schedule, so no `.ko` was needed or loaded.
- **R3 — qualify early apply only if compatible vendor build and wake window are established** (`pending`): opt-in, off after reboot, correct standard brightness behavior, safe stop/revert; replace rather than run alongside the current applier. Primary evidence: lifecycle and readbacks plus optical comparison at first light against stock and the current applier. New DSI sequences or image experiments require exact-operation confirmation.

## Change envelope
Read-only kernel trace probes and reversible stock display actions; sanitized receipts under `artifacts/`, short checkpoint in `WORKSTATE.md`. Any LKM or `msm_drm` change is gated by the preceding evidence. No partition writes, untargeted hardware commands, APK changes, Flicker prevention UI integration or new PWM-frequency claims.

## Current checkpoint
Complete the smallest unresolved outcome first. **R3 qualification only:** reconstruct the pinned CN Kleaf/DDK workspace (match target/variant, headers and vendor symbol versions), build its stock module unmodified, and compare to GLOBAL before patching. The two shipping modules match for all 788 imported CRCs and raw bytes of key wake functions, but not for the whole `.text`. In parallel qualify the optical wake reference before any claim about emission onset. No image or module is ready to load. The phone was restored to the existing userspace applier after removing the probes.
