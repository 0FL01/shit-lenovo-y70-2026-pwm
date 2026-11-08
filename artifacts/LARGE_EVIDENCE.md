# Large unique evidence

This file indexes evidence that is deliberately outside normal Git history.
`git push` does **not** upload these files automatically.

## Git LFS (restored by `git lfs pull`)

Two boot images are tracked with Git LFS. They are the original active `boot_b`
read from the target and the exact persistent KernelSU-Next boot image.

| File | Bytes | SHA256 |
|---|---:|---|
| `artifacts/originals/W3WWS36.65-64-4-1/boot_b.img` | 100,663,296 | `49dcb9dd513ed5b364b9f84c6be4ab7bdc015a50562f5cca4779e46bf9287049` |
| `artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img` | 100,663,296 | `42db701abff335256e41d8b2ce591088512a172c7a4a7af3d37b0d2d489f5c17` |

## GitHub Release `evidence-2026-11-08`

The 21 raw optical recordings are intended to be Release assets, not Git
objects.

- pushed tag: `https://github.com/0FL01/shit-lenovo-y70-2026-pwm/tree/evidence-2026-11-08`
- release URL (to be created): `https://github.com/0FL01/shit-lenovo-y70-2026-pwm/releases/tag/evidence-2026-11-08`
- total: 1,489,668,232 bytes (1420.7 MiB)
- upload status on 2026-11-08: the Git tag and checksum file are pushed, but
  the Release and its assets are **not yet uploaded**. The `GITHUB_TOKEN`
  available in the working environment could read the repository but
  `POST /releases` returned HTTP 403 `Resource not accessible by personal access
  token`. Create the Release with a token that has repository `Contents: write`
  (or upload through the GitHub web UI), then upload the two archives and
  `SHA256SUMS`.

| File | Bytes | SHA256 |
|---|---:|---|
| `artifacts/optical/current_ui_dc_reference_20261106.mp4` | 43,511,033 | `f3bc8e163203205a422bf118bd4b4a1726e20fa0e3ddcfa6fa0c5ce2ff5c3e3e` |
| `artifacts/optical/pacman_boundary_20261106.mp4` | 46,690,837 | `5c0b3f25f7c3f78a0800d156cd1b4cdda2644ed7eb3e81c6d314157febc3b8fb` |
| `artifacts/optical/pacman_dc_manual_20261106.mp4` | 42,451,371 | `127064f5f70bf98f46ec62171530d28893acffb5056d3933d0422beba2aa4505` |
| `artifacts/optical/pacman_dsi_blocks_20261106.mp4` | 82,975,715 | `ea2c2c4687f913eed38a4c4ab1bf575c9e53995bed9e8bbe1cc6e23c407851c6` |
| `artifacts/optical/pacman_dsi_blocks_redraw_20261106.mp4` | 178,509,912 | `9fd82f6d2e93b86b04e5ee2d809f710344e3e96098e2762172de4d553362deef` |
| `artifacts/optical/pacman_dsi_coupled_on_20261107.mp4` | 64,885,511 | `0236060fa61d898e14b3f234ade26d97be5b65b7b76bec85fb3c6b07ec3c84ba` |
| `artifacts/optical/pacman_dsi_mode90_20261106.mp4` | 39,096,951 | `be2f65645f1e3e09e4ff6281e0279b1f2a625e42bec3735bc88350eba6175b4b` |
| `artifacts/optical/pacman_dsi_selector_split_20261107.mp4` | 103,796,146 | `90daf4317ecabced137a38c403f4653f7d77d2649acf044b0eaacf3be504af2a` |
| `artifacts/optical/pacman_dsi_stock_on_20261106.mp4` | 39,848,686 | `00c854fcf32b2f21e24476f5e20b86e608156bc1d0c504a475040cd5d6c4678f` |
| `artifacts/optical/pacman_dsi_stock_on_dbv_20261106.mp4` | 40,579,062 | `8663e3f221388ae1d79457afb012c06177b30f7e0558c19a88cac809c6f52837` |
| `artifacts/optical/pacman_dsi_stock_on_redraw_20261106.mp4` | 72,163,920 | `d6346c9c3013af972d61bf8cdddcbe41d4fff48a4a98a1bb5d305ae8af08ea17` |
| `artifacts/optical/pacman_dsi_transport_cli_failure_20261106.mp4` | 52,619,453 | `ad264c0c2e94b5f60ab2a5c86c189e7336d97177573d84eaf34f9bb0939fc33e` |
| `artifacts/optical/pacman_exact_dbv_20261106.mp4` | 39,681,817 | `61f47b71fb25c66a5d3c932081cba7f79920873a394241da4f9fb5f02dd2bfb2` |
| `artifacts/optical/pacman_exposure_20261106.mp4` | 44,829,190 | `f4e945574245b2fddb2465cf488650fa22ed1296681c614a8fa0e21edbafc934` |
| `artifacts/optical/pacman_exposure_notch_20261107.mp4` | 125,082,488 | `cbb5fed9a885737641f4f7277fd7af4c4eccc6ef37485edf1a8041168d277bbf` |
| `artifacts/optical/pacman_exposure_notch_supported_20261107.mp4` | 229,412,899 | `f5947375bb28540deab421d992aaa6c34d9d1e56d1f19da44120d37cb8e2645c` |
| `artifacts/optical/pacman_minimum_20261106.mp4` | 31,872,825 | `4727d6aced276496795896f87d4b92b0a6befe37c12780145db9fde070f1b191` |
| `artifacts/optical/pacman_readout_A1_20261106.mp4` | 13,893,933 | `9bf1711d42275bd7568e47d457e389f721305c8f49cbb780713607fc535951fa` |
| `artifacts/optical/pacman_readout_A2_20261106.mp4` | 13,857,163 | `46d45e3dd9bc02b3436eab89502782853df685bacdc476caa583b38e24f7bf83` |
| `artifacts/optical/pacman_readout_B_20261106.mp4` | 73,749,653 | `c72e8cfcf8127c83c225dbe68ea912b38eb160e6e7c3975b0665dcfeba033aeb` |
| `artifacts/optical/pacman_stock_base_rates_20261107.mp4` | 110,159,667 | `935d71cab6b8c4049bd6e7435c8df20da3677653ecba8aee5d9e2eba635f9ad7` |

## Why these are not in normal Git

- Each MP4 is larger than GitHub's 100 MiB normal-file limit; the set totals
  about 1.42 GiB, above the free Git LFS quota.
- The two boot images total 192 MiB and are kept in Git LFS, within the free
  1 GiB LFS allowance.
- The recordings are primary optical evidence; they are not re-downloadable.

## Build the release archives

Run from the repository root; write archives outside the work tree:

```bash
REL="${XDG_CACHE_HOME:-$HOME/.cache}/legion-y70-release-20261108"
mkdir -p "$REL"

tar -C /mnt/kston/legion-Y70-madness -cf "$REL/optical-videos-20261108.tar" \
  artifacts/optical/*.mp4

tar -C /mnt/kston/legion-Y70-madness -cf "$REL/boot-images-20261108.tar" \
  artifacts/originals/W3WWS36.65-64-4-1/boot_b.img \
  artifacts/kernel/gki_r59/kernelsu_next/persistent/boot.img

cd "$REL"
sha256sum *.tar > SHA256SUMS
```

Upload `optical-videos-20261108.tar`, `boot-images-20261108.tar` and
`SHA256SUMS` to the `evidence-2026-11-08` release. Then verify:

```bash
cd "$REL"
sha256sum -c SHA256SUMS
```

## Per-file integrity

`artifacts/large_evidence_sha256.txt` contains the SHA256 of every file listed
above. Verify the local copies with:

```bash
cd /mnt/kston/legion-Y70-madness
sha256sum -c artifacts/large_evidence_sha256.txt
```

The LFS images are the canonical rollback/reinstall copies. Do not substitute a
freshly built image without verifying the build and the target A/B slot.
