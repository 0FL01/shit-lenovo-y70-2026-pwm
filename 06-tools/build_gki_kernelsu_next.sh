#!/usr/bin/env bash
# Root-only kernel build. No boot image packaging, device writes or display edits.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace="$root/sources/gki-15950084"
ksu="$root/sources/KernelSU-Next-v3.4.2"

[[ $(git -C "$workspace/common" rev-parse HEAD) == 09eda8c8505ac19be9c4e063afa1d351c1ca9fe2 ]]
[[ $(git -C "$workspace/build/kernel" rev-parse HEAD) == a71b075c1d43d226779d2e834433e7a1d1885beb ]]
[[ $(git -C "$ksu" rev-parse HEAD) == 4c706b5938665866ebe16944a481a7b91e3396af ]]
[[ $(git -C "$ksu" rev-list --count HEAD) == 3355 ]]
git -C "$workspace/build/kernel" diff --quiet HEAD
git -C "$ksu" diff --quiet HEAD
git -C "$workspace/common" diff --binary HEAD | cmp -s "$root/artifacts/kernelsu_next_patch.diff" -
[[ $(readlink -f "$workspace/common/drivers/kernelsu") == "$ksu/kernel" ]]
cmp -s "$workspace/common/certs/google_gki_r59.pem" "$root/artifacts/kernel/gki_r59/google_module_signing_cert.pem"

cd -- "$workspace"
export BUILD_NUMBER=15950084
exec tools/bazel build \
  --config=release \
  --extra_git_project=common --extra_git_project=build/kernel \
  --jobs=6 --make_jobs=6 \
  //common:kernel_aarch64
