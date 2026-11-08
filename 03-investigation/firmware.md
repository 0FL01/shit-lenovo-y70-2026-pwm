# Firmware acquisition and offline cross-region diff

## A. Sources that exist

### Exact physical SKU, China RETCN

Source index: https://mirrors.lolinet.com/firmware/lenowow/2026/Legion_Y70_2026/XT2611-1/

- `XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip` (about 14.9 GB listed as KB in mirror).
- `XT2611-1_AVR_RETCN_16_W3WWL36.65-48-7_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip` (about 15.0 GB).

### Related hardware SKU, global RETEU

Source index: https://mirrors.lolinet.com/firmware/lenomola/2026/avr/official/TELEU/

- `XT2611-3_AVR_RETEU_16_W3WW36.65-25-3-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip` (about 9.8 GB).
- `XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip` (about 13.5 GB).

These are **different model numbers**. Offline compare only.

Read-only ADB on 2026-10-28 (`confirmed-on-target`, `artifacts/device_inventory.json`)
identified the pre-OTA global build as **`W3WW36.65-64-4`**, carrier `teleu`,
on boot hardware SKU **XT2611-1**, revision `pvt`. The second archive is now analyzed:
its fingerprint/kernel and 11 saved vendor fingerprints match that historical inventory.
This is not full image equivalence or a trusted backup for XT2611-1.
At 20:03 UTC read-only ADB confirmed **`W3WWS36.65-64-4-1`**, kernel
`g09eda8c8505a-ab15950084`, slot `_b`; the downloaded ZIP is not this newer OTA.
Keep CN `W3WWL36.65-11-18` as the source-tagged baseline.

## B. Input manifest and integrity

CN display-related inventory/extraction is complete: `artifacts/firmware_manifest.json`,
`artifacts/cn_panel_commands.md` and `.json`. Root: `extracted/XT2611-1/W3WWL36.65-11-18/`.
Super reconstructed with native simg2img; five EROFS partitions now extracted without root,
including system_a added for the framework trace. GLOBAL root:
`extracted/XT2611-3/W3WW36.65-64-4/`, with 34 sparsechunks, five EROFS partitions and
selected vendor_boot files. GLOBAL inventory: `artifacts/eu_panel_commands.md` and
manifest `global_reference`. All 18 BOE DC arrays match CN, but 36 init/timing properties
differ in ILI97701A v2-v4. Details: `artifacts/display_diffs.md` and
`artifacts/regional_dtbo_diff.json`. No full driver build or current-OTA match is implied.

- Preserve source URLs, raw filenames and download resume; store URL, model, region, build, size, download date and archive listing in `artifacts/firmware_manifest.json`. Calculate a checksum only to verify integrity or answer a concrete binary-comparison question; no routine per-file checksum manifests.
- Check available disk space (large archives + unpacking can require tens of GB), and record exact tool versions.
- Use read-only archive listing first: `7z l ROM.zip` or `unzip -l ROM.zip`.
- Determine whether package is Motorola XML service fastboot with sparsechunks, `super.img`, individual images, or OTA payload; choose corresponding extractor. **Do not assume payload.bin**.
- Scripts embedded in ROM ZIP or service flashing XML are parsed and inventoried offline; they are not executed on the phone.
- Preserve partition names and any checksums used for a specific comparison; avoid silently merging per-SKU partitions.

## C. Extraction algorithm

1. Search archive list for `flashfile.xml`, `servicefile.xml`, `boot.img`, `init_boot.img`, `vendor_boot.img`, `dtbo.img`, `vbmeta*.img`, `vendor_dlkm`, `odm_dlkm`, `super*.img`, `system*.img`, `vendor*.img`, `odm*.img`, `payload.bin` and `*.bin`.
2. If package has several Motorola `super.img_sparsechunk.*`, reconstruct sparse image with the correct sparse-aware tooling; verify header and partition table. Do not treat chunks as raw concatenable data without proving format.
3. If `super.img` is Android sparse, use `simg2img` before `lpunpack`; use `lpdump` for metadata, confirm partitions and slots. If OTA payload, use a trusted payload extractor that validates operations.
4. If Device Tree overlay is available, inspect `dtbo.img` with AOSP `mkdtboimg.py dump` / `dtc` (and dump multiple individual DTBs). `fdtdump` and `fdtget` may be useful; verify files are DTB, not wrapped images.
5. For `boot`, `init_boot`, `vendor_boot`, use AOSP `unpack_bootimg.py` and record boot header, kernel version, ramdisk, vendor ramdisk fragment table, dtb locations, compression and sizes.
6. For vendor/product/odm EROFS or ext4, mount **read-only** through loop device (if available) or extract using dedicated tooling; record relevant file paths. Hash only files needed for a concrete integrity check or binary comparison. Don't execute extracted binaries.
7. Identify display binaries/configs, DT properties and overlay APKs. Compare by partition and region, not blanket whole-ROM diff.

## D. Comparisons to automate

- Matching panel `compatible` names, panel ID thresholds, revisions, `qcom,mdss*`, `dsi_*`, `dsc`, `panel_timing`, `te`, brightness level maps, gamma tables and any `pwm`, `flicker`, `dc`, `low_light`, `dimming`, `backlight` properties.
- `vendor/etc/display*`, `odm/etc/display*`, `vendor/etc/init*`, `odm/etc`, `product/overlay`, `system_ext/overlay`, device-specific XML/properties; search binary symbols and strings only as pointers — on their own they are not proof of behavior.
- Vendor display libs, HAL service declarations and build IDs; compare binary sizes, `sha256`, `readelf -Ws` symbol differences. For ARM64 stripped libs use installed headless Ghidra 12.1.4 via `~/tools/ghidra-12.1.4-pyvenv/bin/python 06-tools/ghidra_decompile.py symbols BINARY --output artifacts/ghidra_toolkit_20261107/CASE --timebox 300` (from repo root); `decompile BINARY --function NAME` uses the same output/timebox options. `.gnu_debugdata` symbols are imported automatically, not DWARF types; projects/temp are external and exports retain binary/version provenance. Known-answer validation: `artifacts/ghidra_toolkit_20261107/result.md`; decompiler output still requires independent semantic verification and does not decode DDIC registers.
- Diff init scripts to see whether `Flicker prevention` maps to a property/property-trigger and a sysfs node.
- Compare kernel module lists and kernel ELF strings; parse modules through `modinfo`, matching `vermagic` / fingerprint.
- Document **confirmed identical** binary files separately from files changed across variants. Exact same panel timing/command bytes may weaken region-specific hypothesis.

## E. Build-source compatibility

Downloaded CN boot confirms `6.12.58-android16-6-g18b507169406-ab14630870-4k`.
Identical msm_drm copies are in CN vendor_boot ramdisk and vendor_dlkm; vermagic
`6.12.58-android16-6-maybe-dirty-4k SMP preempt mod_unload modversions aarch64`.
Neither the duplicate nor the base version proves compatibility with GLOBAL.

GLOBAL reference contains kernel `gb0a9599c6c01-ab14987696`, msm_drm 6 071 656 bytes,
build ID `8c58ca326e99f7c98644d723230b40a7686dee81`; it differs from CN.
Seven checked vendor display ELFs are byte-equal between archives. Matching vermagic
or selected instruction bodies still does not prove ABI/KMI or equality with the
post-OTA loaded module. Embedded AVB top/system keys match, but archive rollback
indices are CN 0 / GLOBAL 2 and HAB CID metadata is 11 / 50. Signatures, target
rollback counters and cross-SKU boot compatibility remain unverified.

Motorola official tag `MMI-W3WWL36.65-11-18` corresponds to China W3WWL36.65-11-18 request, **not an established source match for the current OTA**. Current target `uname` is `6.12.58-android16-6-g09eda8c8505a-ab15950084-4k`; the CN and downloaded GLOBAL kernel strings differ. Target `msm_drm` is loaded as a module, but its current bytes/vermagic and kernel config are not established. Exact `MMI-W3WW36.65-64-4` tag-prefix queries returned no refs in display-devicetree and techpack-display; this does not exclude other tags/branches. Verify module versions, config, GKI / KMI and exact current stock image. A successful compilation does not guarantee a bootable or compatible image.

## F. Explicit exclusion

`XT2611-3`/`RETEU` images serve as offline references; writing them to `XT2611-1` is out of scope for this plan. Region swap (including boot, dtbo, vbmeta, partitions) is its own research track with source verification and a separately owner-confirmed stage; it is not the first solution.
