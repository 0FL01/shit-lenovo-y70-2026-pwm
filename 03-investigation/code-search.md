# Source / binary hunting map

## 0. Hardware orientation

Target family: Qualcomm Snapdragon 8 Gen 5, Android 16, Linux kernel reported as 6.12.58 for one XT2611-1 build. Firmware codename: `avr`. Search `avr`, `AVR` and the marketed/variant model strings. Target panel has been described as BOE Q10 in Chinese reviews, but verify exact controller and revision. Hardware revision `PVT` is not a panel ID.

## 1. Public source priorities

1. `MotorolaMobilityLLC/kernel-msm` tag `MMI-W3WWL36.65-11-18`: https://github.com/MotorolaMobilityLLC/kernel-msm/releases/tag/MMI-W3WWL36.65-11-18
2. `MotorolaMobilityLLC/kernel-display-devicetree`: https://github.com/MotorolaMobilityLLC/kernel-display-devicetree
3. `MotorolaMobilityLLC/kernel-devicetree`: https://github.com/MotorolaMobilityLLC/kernel-devicetree
4. **Located 2026-10-28:** `MotorolaMobilityLLC/kernel-msm-5.4-techpack-display`, tag `MMI-W3WWL36.65-11-18`, commit `fa008c43c070ff20faa33853649f5dfd4c427e99`: actual `msm/dsi/dsi_panel.c`, `msm/dsi/dsi_display.c`, `msm/sde/` native DC implementation. Repository name `5.4` is not a kernel-version assertion. Pinned lines and matching limits: `artifacts/driver_callgraph.md`.
5. Other Motorola/Qualcomm sources and proprietary blobs remain references; verify device/version applicability before expanding the search.

Offline update 2026-10-28 (`reported`): all 18 BOE DC arrays match CN/GLOBAL reference,
but ILI97701A v2-v4 init/timing-switch do not. Source/data matching must stay property-specific.
GitHub `git/matching-refs/tags/MMI-W3WW36.65-64-4` returned HTTP 200 / `[]` in
`kernel-display-devicetree` and `kernel-msm-5.4-techpack-display`; the known CN
`MMI-W3WWL36.65-48-7` prefix also returned no display-devicetree refs. These are
bounded tag-prefix checks, not an exhaustive source-availability claim.

Search candidate paths, but do not assume they exist in a given tag:

- `drivers/gpu/drm/msm/`, `techpack/display/`, `drivers/gpu/drm/`.
- `drivers/gpu/drm/msm/disp/dpu1/`, `dsi/`, `panel/`, `drm_panel*`, `dsi_panel*`.
- `arch/arm64/boot/dts/qcom/`, `dts/`, `*.dtsi`, `*.dtso`.
- vendor/out-of-tree Qualcomm display module sources and `.ko` blobs in `vendor_dlkm` or `odm_dlkm`.

## 2. Search strings (broad, then narrowed)

```bash
rg -n -i --glob '*.{c,h,cc,cpp,rs,dts,dtsi,dtso,xml,rc,prop,conf,json}' \
  '(pwm|flicker|anti.flicker|dc[_-]?dimm|dimlayer|dimming|backlight|brightness|hbm|fod|aod|doze|low.light)' \
  sources extracted | head -n 800

rg -n -i '(boe|q10|panel[_ -]?id|panel[_ -]?name|mdss[_-]?dsi|dsi[_-]?panel|mipi[_-]?dsi|display[-_]?mode)' \
  sources extracted | head -n 800
```

`head` is only a navigation aid: save full matches to files and search for false positives; don't prematurely stop scan at first hit. Motorola kernel may be a platform tree, and panel driver may be a vendor module or binary in ROM.

## 3. ADB inventory before source hunting

Use `06-tools/collect_readonly.sh` on Fedora. Report:

- actual `ro.product.*`, `ro.vendor.*`, build fingerprint, release, kernel `uname -a`;
- bootloader state from `ro.boot.*` and optional fastboot read-only (`getvar securestate`, `getvar current-slot`, `getvar product`, etc.); **do not infer unlock state from `pvt`**;
- display panel identifiers from `dmesg` (root may be needed), `/sys/class/drm`, `/sys/class/backlight`, `/proc/device-tree` (with cautious byte handling), `dumpsys display`, `dumpsys SurfaceFlinger`, vendor properties;
- observed system settings name changed by toggling Flicker prevention (owner controls toggle manually; agent only reads before and after);
- optional HAL/binder via `lshal`, `service list`, `/vendor/etc/vintf/manifest.xml`, `dumpsys`.

Raw device logs are shared only after removing IMEI, serial, Android IDs, SSID, token, MAC. Collection script records only selected properties, but inspect output before sharing.

## 4. Display-path trace (evidence chain)

User's `Flicker prevention` UI component -> framework / SystemUI settings provider -> vendor property / binder service -> display HAL (possibly Qualcomm SDM or Motorola wrapper) -> kernel ioctl/sysfs/DRM properties -> panel state machine -> MIPI DSI command(s) -> optically measured waveform.

For each hop record: file path, symbol, full call graph, input conditions, current / modified values, command bytes and explanatory confidence. If any hop is closed-source, use correlated settings toggles, logged property effects, binary strings and analysis, but mark interpretation as inference.

Inspect Display HAL libraries with `file`, `readelf`, `nm -D`, `strings`; ARM64 code-level RE now uses installed headless Ghidra 12.1.4: `~/tools/ghidra-12.1.4-pyvenv/bin/python 06-tools/ghidra_decompile.py decompile BINARY --function NAME --output artifacts/ghidra_toolkit_20261107/CASE --timebox 300` (from repo root). `functions`/`symbols` list imported names (`--filter TEXT`); `decompile`/`xrefs` accept an exact `--function NAME` or hex Ghidra `--address` (containing function for decompile, exact address for xrefs). Projects/JVM temp stay in external approved cache, JSON/C carry provenance; ET_REL addresses are block+offset, not live kernel VA. See `artifacts/ghidra_toolkit_20261107/result.md` for validation and limitations. For DTS, separate stock code from overlay and check compatible panel IDs; data-level Python and independent DDIC-semantic checks remain necessary.

Resolved reference path (`W3WW36.65-64-4`): `CoreSettingsExt.DisplayDCMode` writes
**Motorola** Global `display_dc_mode_enabled`, authority
`com.motorola.android.providers.settings`, not AOSP Settings.Global.
Provider notification reaches `com.motorola.server.display.PanelsService` in
`system_a/system/framework/services.jar!classes3.dex`; its native call is at DEX
offset `0x2d1120`. JNI table in `libandroid_servers.so` maps `(I)V` to VA `0xc81e0`.
System AIDL V1 → vendor V2 → legacy displaypanel → DRM DC ioctl is statically traced.
Full evidence and errors/lifecycle: `artifacts/driver_callgraph.md`.
Current post-OTA `GET_global` returned value 1, but the old reference does not prove
the current implementation or successful DSI application.

## 5. Panel control conditions to map

- Screen initial boot, blank/unblank, reboot/resume.
- Changing manual vs automatic brightness, possibly separate panel modes above/below thresholds.
- 1/60/90/120/144 Hz LTPO transitions. Refresh rate != PWM, but transitions can change dimming state.
- HBM/HDR, local HBM for under-display fingerprint, thermal limits, AOD/doze.
- Flicker prevention / DC dimming toggles from both regions.
- Bit depth, gamma, TE/vsync, DSC and panel unlocking/latching sequences.

## 6. Stop criteria

If driver and DSI map are only in inaccessible closed binary, report constraint and possible low-risk next evidence. Random DSI command fuzzing is not part of the methodology; the default path starts from captured stock mode values and tests only vendor-known presets with optical measurement and immediate rollback.
