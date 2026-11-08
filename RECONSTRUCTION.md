# Reconstruction guide

This repository contains the research record, tools and text evidence for the
Lenovo XT2611-1 / Motorola `avr` display-PWM investigation. It intentionally
does **not** contain multi-gigabyte external inputs or build outputs. This file
records how to restore them.

Status convention: `confirmed-on-target`, `confirmed-other-device`, `reported`,
`hypothesis`, `unknown`. The device facts and their provenance remain in
`00-facts/`, `artifacts/device_inventory.json` and the dated reports.

## 1. Policy

Ignored by `.gitignore`:

- `downloads/` — vendor service ZIPs, GKI ZIP, KernelSU-Next APK and RPM tools;
- `extracted/` — unpacked ROM trees, including `super.raw.img`;
- `sources/` — public AOSP GKI and KernelSU-Next checkouts, plus the local
  KernelSU patch applied to the GKI tree;
- `.venv/` — Python environment;
- firmware images and kernel build outputs that are re-creatable;
- vendor `.so` files extracted from the ROM;
- raw optical `.mp4` recordings, which are distributed as GitHub Release assets;
- `artifacts/key` — the device-specific bootloader unlock key.

Tracked with Git LFS:

- `artifacts/originals/W3WWS36.65-64-4-1/boot_b.img` — original active `boot_b`
  read from the target device before the persistent KernelSU install;
- `artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img` — the exact
  KernelSU-Next boot image installed on the device.

Both are unique recovery artefacts. Their acquisition/install metadata remains
in the adjacent JSON files and in `artifacts/flash_proposal.md`.

## 2. Host prerequisites

The recorded work used a Fedora-family host with:

- Python 3.13.5;
- `numpy==2.4.4`, `Pillow==12.1.1` (see `requirements.txt`);
- `adb` and `fastboot` (Android platform-tools);
- `7z`/7-Zip, `simg2img`, `fsck.erofs` (erofs-utils), `unzip`;
- Ghidra 12.1.4 in `~/tools/ghidra-12.1.4-pyvenv` for
  `06-tools/ghidra_decompile.py`;
- Git and Git LFS.

The Python environment is recreated with:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. External inputs

### 3.1 Firmware service ZIPs

| Path | Bytes | Source |
|---|---:|---|
| `downloads/XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip` | 14 918 250 042 | `https://mirrors.lolinet.com/firmware/lenowow/2026/Legion_Y70_2026/XT2611-1/XT2611-1_AVR_RETCN_16_W3WWL36.65-11-18_subsidy-DEFAULT_regulatory-DEFAULT_CFC.xml.zip` |
| `downloads/XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip` | 13 483 677 726 | `https://mirrors.lolinet.com/firmware/lenomola/2026/avr/official/TELEU/XT2611-3_AVR_RETEU_16_W3WW36.65-64-4_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip` |

The XT2611-3 archive is an offline reference only. It is not a verified backup
or flash candidate for the XT2611-1 target.

Member sizes, extraction roots and the original extraction result are in
`artifacts/firmware_manifest.json` (`extraction` section). The CN tree was
produced from 46 selected ZIP members; `super.raw.img` was reconstructed with
native `simg2img` over all 36 sparse chunks in numeric order, and the EROFS
partitions were extracted with `fsck.erofs`. Do not concatenate sparse chunks.

### 3.2 Google GKI reference

| Path | Bytes | Source |
|---|---:|---|
| `downloads/gki-certified-boot-android16-6.12-2025-12_r59.zip` | 16 829 063 | `https://dl.google.com/android/gki/gki-certified-boot-android16-6.12-2025-12_r59.zip` |

- Member used: `boot-6.12.img` (67 108 864 bytes).
- Kernel build: `15950084`, tag `android16-6.12-2025-12_r59`,
  commit `09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`.
- Provenance and CRC result: `artifacts/kernel/gki_r59/acquisition.json`.
- This is a Google reference component, **not** a Motorola partition original and
  not a flash candidate.

### 3.3 KernelSU-Next release APK

| Path | Bytes | Source |
|---|---:|---|
| `downloads/KernelSU_Next_v3.4.2_33355-release.apk` | 16 682 167 | `https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.4.2/KernelSU_Next_v3.4.2_33355-release.apk` |

SHA256 `774a5511f7034a4930e881114e202319cbdc34c5aaaa5c7c6b6d2902364e4c58`.
This is the normal (non-spoofed) Manager APK. The v2 signer certificate is
`artifacts/kernel/kernelsu_next_manager_cert.der`; its SHA256 matched the pinned
KernelSU Kbuild certificate. Full host APK signature verification was not run;
native PackageManager verification on installation remains mandatory. The APK
was not installed as part of the source audit.

### 3.4 Kernel source workspace

`sources/gki-15950084/` is a Kleaf workspace assembled from the pinned Google CI
manifest:

- manifest: `artifacts/kernel/gki_r59/manifest_15950084.xml`
  (50 projects, full revisions);
- `common`: `09eda8c8505ac19be9c4e063afa1d351c1ca9fe2`;
- `build/kernel`: `a71b075c1d43d226779d2e834433e7a1d1885beb`;
- the manifest came from
  `https://ci.android.com/builds/submitted/15950084/kernel_aarch64/latest/manifest_15950084.xml`.

The local `common` tree contains the KernelSU integration. The complete diff is
`artifacts/kernelsu_next_patch.diff` (3 950 bytes). During the recorded work it
was verified byte-identical to:

```bash
git -C sources/gki-15950084/common diff --binary HEAD | cmp -s artifacts/kernelsu_next_patch.diff -
```

That check returned `0` (`cmp` equal). Re-apply the patch only after checking the
pinned HEADs. `06-tools/build_gki_baseline.sh` expects a clean tree;
`06-tools/build_gki_kernelsu_next.sh` expects the patched tree.

The KernelSU-Next source is a separate clean checkout:

- `sources/KernelSU-Next-v3.4.2`;
- commit `4c706b5938665866ebe16944a481a7b91e3396af`;
- tag `v3.4.2`, upstream code 33355, 3355 ancestors;
- provenance: `artifacts/kernel/kernelsu_next_source.json` and
  `artifacts/kernel/kernelsu_next_version_metadata.json`.

The build scripts check the exact commits, the clean KernelSU tree, the exact
patch and the public Google certificate before invoking Bazel:

```bash
bash 06-tools/build_gki_baseline.sh
bash 06-tools/build_gki_kernelsu_next.sh
```

The second script expects the KernelSU checkout at
`sources/KernelSU-Next-v3.4.2` and the symlink `common/drivers/kernelsu` to its
`kernel/` directory, exactly as described in `artifacts/source_inventory.md`.

### 3.5 RPM tools

| Path | Source |
|---|---|
| `downloads/tools/erofs-utils-1.7.1-1.el9.x86_64.rpm` | `https://dl.fedoraproject.org/pub/epel/9/Everything/x86_64/Packages/e/erofs-utils-1.7.1-1.el9.x86_64.rpm` |
| `downloads/tools/erofs-utils-1.9.1-1.fc44.x86_64.rpm` | `https://kojipkgs.fedoraproject.org/packages/erofs-utils/1.9.1/1.fc44/x86_64/erofs-utils-1.9.1-1.fc44.x86_64.rpm` |

The 1.7.1 EPEL RPM was the usable extraction tool; the 1.9.1 attempt is retained
only as provenance in `artifacts/firmware_manifest.json`.

## 4. Large unique evidence

Raw optical recordings (21 MP4 files) and the two LFS boot images are outside
normal Git history. The recordings are intended to be distributed as GitHub
Release assets under the tag `evidence-2026-11-08`; the tag and checksum file are
pushed, but the Release asset upload is still pending because the available token
lacks release permission. See `artifacts/LARGE_EVIDENCE.md` for the current
status, file list, SHA256 manifest and extraction commands.

If the release assets are unavailable, the original files remain in the local
workspace at:

- `artifacts/optical/*.mp4`;
- `artifacts/originals/W3WWS36.65-64-4-1/boot_b.img`;
- `artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img`.

The LFS images are the canonical rollback/reinstall copies. Do not replace them
with a freshly built image without verifying the build and the target A/B slot.

## 5. Minimal verification after clone

```bash
git lfs pull
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
OPENBLAS_NUM_THREADS=2 .venv/bin/python -m unittest discover -s 06-tools -p 'test_*.py' -v
```

Expected result from the recorded workspace: 29 tests run, 2 Ghidra
known-answer tests skipped (`GHIDRA_TOOLKIT_KNOWN_ANSWER=1` enables them). The
full GKI rebuild is optional and requires the external source workspace and
toolchain; it is not part of a text-only clone.

## 6. Security and privacy

- The bootloader unlock key is deliberately absent. It is stored outside the
  repository (mode 0600) and is also covered by `.gitignore`.
- IMEI, serial numbers, Android ID, MAC addresses, SSIDs, tokens and panel cell
  IDs are not retained in the published inventory; see
  `artifacts/device_inventory.json` (`collection.privacy`).
- Vendor `.so` files and ROM images are not redistributed.
- Optical recordings may contain UI content; review them before making the
  repository public.
- LMSA/OTA credentials and private responses are outside the workspace and are
  not part of this repository.
