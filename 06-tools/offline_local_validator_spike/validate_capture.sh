#!/bin/sh
# Offline files only. Never invokes a child, device, transport, or recovery.
set -eu
export LC_ALL=C
[ "$#" = 5 ] || exit 2
[ "$5" = 0 ] || exit 2
f=$1; err=$2; nonce=$3; kind=$4
case "$f" in /*) ;; *) exit 2;; esac
case "$err" in /*) ;; *) exit 2;; esac
# Staging owner must provide immutable files in an owned, non-writable-by-others
# directory. Checks below alone do not prevent a hostile same-UID TOCTOU race.
for p in "$f" "$err"; do
 [ -f "$p" ] && [ ! -L "$p" ] || exit 2
 [ "$(stat -c %u "$p")" = "$(id -u)" ] || exit 2
 [ "$(stat -c %a "$p")" = 600 ] || exit 2
 [ "$(stat -c %h "$p")" = 1 ] || exit 2
done
[ "$(wc -c < "$err")" = 0 ] || exit 2
[ "$(wc -c < "$f")" -le 262144 ] || exit 2
# Byte-level strict subset of UTF-8: printable ASCII, LF and TAB only.
# No shell variable ever contains evidence. cmp sees original exact bytes.
umask 077
w=$(mktemp -d) || exit 2
cleanup() { s=$?; trap - EXIT HUP INT TERM; rm -f "$w/ascii" "$w/normalized" "$w/errors" || s=2; rmdir "$w" || s=2; exit "$s"; }
trap cleanup EXIT
trap 'exit 2' HUP INT TERM
tr -cd '\011\012\040-\176' < "$f" > "$w/ascii" 2> "$w/errors" || exit 2
[ ! -s "$w/errors" ] && cmp -s "$f" "$w/ascii" || exit 2
awk '{print}' "$f" > "$w/normalized" 2> "$w/errors" || exit 2
[ ! -s "$w/errors" ] && cmp -s "$f" "$w/normalized" || exit 2
awk -v nonce="$nonce" -v kind="$kind" -f "$(dirname "$0")/capture.awk" "$f"
