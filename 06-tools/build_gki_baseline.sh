#!/usr/bin/env bash
# Unmodified GKI reproduction only: no Motorola boot packaging or device writes.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace="$root/sources/gki-15950084"

[[ $(git -C "$workspace/common" rev-parse HEAD) == 09eda8c8505ac19be9c4e063afa1d351c1ca9fe2 ]]
[[ $(git -C "$workspace/build/kernel" rev-parse HEAD) == a71b075c1d43d226779d2e834433e7a1d1885beb ]]
git -C "$workspace/common" diff --quiet HEAD
git -C "$workspace/build/kernel" diff --quiet HEAD

cd -- "$workspace"
# Preserve the reference build label for comparison; this is a local reproduction.
export BUILD_NUMBER=15950084
exec tools/bazel build \
  --config=release \
  --extra_git_project=common --extra_git_project=build/kernel \
  --jobs=6 --make_jobs=6 \
  //common:kernel_aarch64
