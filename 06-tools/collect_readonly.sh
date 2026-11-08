#!/usr/bin/env bash
# Collect selected non-mutating Android display/build data over ADB.
# Read-only collection: no writes, no reboots; device settings unchanged.
set -Eeuo pipefail

if ! command -v adb >/dev/null 2>&1; then
  echo 'ERROR: adb unavailable (install Android platform-tools).' >&2
  exit 2
fi

out="${1:-$(pwd)/artifacts/adb-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$out"

if ! adb get-state 2>/dev/null | grep -qx device; then
  echo 'ERROR: no authorized ADB device. Use adb devices and authorize USB debugging.' >&2
  exit 3
fi

printf '%s\n' 'XT2611-1 read-only collection' "UTC: $(date -u +%FT%TZ)" > "$out/collection.txt"
adb shell uname -a > "$out/uname.txt" 2>&1 || true
adb shell getprop ro.build.display.id > "$out/display-build.txt" 2>&1 || true

# Read individual keys only; full getprop dumps are skipped (may contain sensitive fields).
properties=(
  ro.product.model ro.product.device ro.product.vendor.device
  ro.product.manufacturer ro.product.board
  ro.build.fingerprint ro.vendor.build.fingerprint
  ro.build.version.release ro.build.version.incremental
  ro.boot.hardware.revision ro.boot.hardware
  ro.boot.verifiedbootstate ro.boot.vbmeta.device_state
  ro.boot.flash.locked ro.boot.slot_suffix
  ro.build.version.security_patch ro.vendor.build.security_patch
)
: > "$out/selected-props.txt"
for key in "${properties[@]}"; do
  value="$(adb shell getprop "$key" 2>/dev/null | tr -d '\r' || :)"
  printf '%s = %s\n' "$key" "$value" >> "$out/selected-props.txt"
done

# Keep both raw setting snapshots. The user may manually toggle Flicker prevention
# and run collection again for before/after comparisons.
for ns in system secure global; do
  adb shell settings list "$ns" 2>/dev/null \
    | grep -Ei 'flicker|anti.?flicker|dimm|pwm|refresh_rate|display' \
    > "$out/settings-${ns}-filtered.txt" || :
done

adb shell 'ls -la /sys/class/backlight /sys/class/drm /sys/class/leds 2>/dev/null' \
  > "$out/sys-class-list.txt" 2>&1 || true
adb shell 'ls -la /dev/block/by-name 2>/dev/null' \
  > "$out/partition-names.txt" 2>&1 || true
adb shell 'ls -la /proc/device-tree 2>/dev/null' \
  > "$out/device-tree-top.txt" 2>&1 || true

# Diagnostic info may include installed app names; inspect before sharing.
adb shell dumpsys display > "$out/dumpsys-display.txt" 2>&1 || true
adb shell dumpsys SurfaceFlinger > "$out/dumpsys-surfaceflinger.txt" 2>&1 || true
adb shell 'getprop | grep -Ei "display|flicker|dimm|pwm|panel|fps|refresh"' \
  > "$out/props-display-filtered.txt" 2>&1 || true

cat <<MSG
Done: $out
This script did not modify the device.
NOTICE: inspect/sanitize logs before sharing. Do NOT publish serial, IMEI, Android ID or tokens.
MSG
