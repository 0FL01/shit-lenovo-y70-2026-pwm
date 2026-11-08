#!/usr/bin/env bash
# Read-only source/firmware inventory. Writes ONLY into --out directory.
set -Eeuo pipefail
if (( $# < 2 )); then
  echo 'Usage: scan_workspace.sh SOURCE_OR_EXTRACTED_DIRECTORY OUTPUT_DIRECTORY' >&2
  exit 2
fi
root="$(realpath "$1")"
out="$2"
[[ -d "$root" ]] || { echo "Not a directory: $root" >&2; exit 2; }
mkdir -p "$out"
out="$(realpath "$out")"
if [[ "$out" == "$root" || "$out" == "$root"/* ]]; then
  echo 'Output must be outside scanned root to prevent recursive indexing.' >&2
  exit 3
fi

find "$root" -type f -printf '%P\t%s bytes\n' > "$out/file-index.tsv"
find "$root" -type f \( -iname '*panel*' -o -iname '*display*' -o -iname '*dtb*' -o -iname '*vendor*' -o -iname '*boot*' \) \
  -printf '%P\n' > "$out/likely-display-files.txt"
if command -v rg >/dev/null 2>&1; then
  rg --hidden -n -i -m 50 \
    --glob '*.{c,h,cc,cpp,dts,dtsi,dtso,xml,rc,prop,conf,json,txt,md}' \
    '(pwm|flicker|anti.flicker|dc[_-]?dimm|dimming|backlight|brightness|hbm|fod|aod|dsi|boe|panel)' \
    "$root" > "$out/text-hits.txt" || true
else
  echo 'ripgrep not installed; skipping text content search' > "$out/text-hits.txt"
fi
printf 'Files: %s\n' "$(wc -l < "$out/file-index.tsv")"
printf 'Inventory: %s\n' "$out"
