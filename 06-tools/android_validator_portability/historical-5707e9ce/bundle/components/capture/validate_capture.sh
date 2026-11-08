#!/bin/sh
# Offline files only. Success requires final rc0 AND empty caller-visible stderr.
# Verdict text alone is never a receipt. External tools/source/acquisition are
# still trusted dependencies, not authenticated by this wrapper.
set -eu
export LC_ALL=C
[ "$#" = 5 ] || exit 2
[ "$5" = 0 ] || exit 2
f=$1; err=$2; nonce=$3; kind=$4
# Reject raw aliases BEFORE awk -v can interpret backslash/octal/hex escapes.
case "$nonce" in ''|*[!0-9a-f]*) exit 2;; esac
[ "${#nonce}" = 12 ] || exit 2
case "$kind" in write|85|C1) ;; *) exit 2;; esac
case "$f" in /*) ;; *) exit 2;; esac
case "$err" in /*) ;; *) exit 2;; esac
umask 077
set -C
base=${TMPDIR:-/tmp}
case "$base" in /*) ;; *) exit 2;; esac
[ -d "$base" ] || exit 2
# Shell-exclusive bootstrap files precede external metadata commands. Any
# collision fails closed. The caller still owns the trust in the parent path.
audit=$base/.p85-validator-$$.audit
bootstrap=$base/.p85-validator-$$.stdout
w=$base/.p85-validator-$$.work
made_bootstrap=0; made_work=0
: > "$audit" || exit 2
# Keep the regular inode open across final unlink; byte-size tests see LF/NUL
# diagnostics too. This Linux /proc capability is REQUIRED, not presumed.
exec 8>> "$audit" || exit 2
audit_fd=/proc/self/fd/8
cleanup() {
 s=$1; trap - EXIT HUP INT TERM
 if [ "$made_work" = 1 ]; then
  rm -f "$w/meta-out" "$w/meta-err" "$w/meta-canonical" "$w/ascii" "$w/normalized" "$w/errors" >&8 2>&1 || s=2
  rmdir "$w" >&8 2>&1 || s=2
  [ ! -e "$w" ] && [ ! -L "$w" ] || s=2
 fi
 if [ "$made_bootstrap" = 1 ]; then
  rm -f "$bootstrap" >&8 2>&1 || s=2
  [ ! -e "$bootstrap" ] && [ ! -L "$bootstrap" ] || s=2
 fi
 rm -f "$audit" >&8 2>&1 || s=2
 [ ! -e "$audit" ] && [ ! -L "$audit" ] || s=2
 [ -f "$audit_fd" ] && [ ! -s "$audit_fd" ] || s=2
 return "$s"
}
trap 'code=$?; cleanup "$code"; exit $?' EXIT
trap 'exit 2' HUP INT TERM
[ -f "$audit_fd" ] && [ ! -s "$audit_fd" ] || exit 2
: > "$bootstrap" 2>&8 || exit 2
made_bootstrap=1
if mkdir -m 700 "$w" >| "$bootstrap" 2>&8; then made_work=1; else exit 2; fi
[ ! -s "$bootstrap" ] && [ ! -s "$audit_fd" ] || exit 2
# A failing mkdir may have partially executed: never guess that its path is ours
# and delete it. That uncertain remnant is deliberately retained on failure.
checked_meta() {
 if "$@" >| "$w/meta-out" 2>| "$w/meta-err"; then :; else return 2; fi
 [ ! -s "$w/meta-err" ] || return 2
 # Scalar stdout is not trusted until an exact byte comparison against a
 # canonical one-line decimal proves no extra newline, NUL or hidden bytes.
 IFS= read -r meta < "$w/meta-out" || return 2
 case "$meta" in ''|*[!0-9]*|0[0-9]*) return 2;; esac
 [ "${#meta}" -le 10 ] || return 2
 printf '%s\n' "$meta" >| "$w/meta-canonical" || return 2
 if cmp -s "$w/meta-out" "$w/meta-canonical" >&8 2>| "$w/meta-err"; then :; else return 2; fi
 [ ! -s "$w/meta-err" ] && [ ! -s "$audit_fd" ] || return 2
}
# Staging owner must still provide immutable files in an owned parent; these
# checks cannot prevent hostile same-UID TOCTOU or authenticate utility binaries.
checked_meta id -u || exit 2
uid=$meta
for p in "$f" "$err"; do
 [ -f "$p" ] && [ ! -L "$p" ] || exit 2
 checked_meta stat -c %u "$p" || exit 2
 [ "$meta" = "$uid" ] || exit 2
 checked_meta stat -c %a "$p" || exit 2
 [ "$meta" = 600 ] || exit 2
 checked_meta stat -c %h "$p" || exit 2
 [ "$meta" = 1 ] || exit 2
done
checked_meta wc -c < "$err" || exit 2
[ "$meta" = 0 ] || exit 2
checked_meta wc -c < "$f" || exit 2
[ "$meta" -le 262144 ] || exit 2
# Raw evidence never enters a shell variable.
tr -cd '\011\012\040-\176' < "$f" >| "$w/ascii" 2>| "$w/errors" || exit 2
[ ! -s "$w/errors" ] && cmp -s "$f" "$w/ascii" >&8 2>&1 || exit 2
awk '{print}' "$f" >| "$w/normalized" 2>| "$w/errors" || exit 2
[ ! -s "$w/errors" ] && cmp -s "$f" "$w/normalized" >&8 2>&1 || exit 2
# No successful verdict precedes an owned-cleanup failure. The audit FD remains
# valid after unlink for the final validator's status/diagnostic check.
cleanup 0 || exit 2
validator_dir=${0%/*}
[ "$validator_dir" != "$0" ] || validator_dir=.
if awk -v nonce="$nonce" -v kind="$kind" -f "$validator_dir/capture.awk" "$f" 2>&8; then code=0; else code=2; fi
[ -f "$audit_fd" ] && [ ! -s "$audit_fd" ] || code=2
exit "$code"
