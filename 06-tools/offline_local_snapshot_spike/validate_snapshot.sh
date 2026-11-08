#!/bin/sh
# OFFLINE ONLY. Usage: KIND BOOT NEW_STAGE (OUT ERR RC) x 4 or x 1.
# STATE_ONLY order: FIELDS DISPLAY BOOT OWNER. No ESD API or child admission.
set -u
LC_ALL=C; export LC_ALL
umask 077
[ "$#" -ge 3 ] || exit 2
kind=$1; boot=$2; stage=$3; shift 3
case "$kind" in
 STATE_ONLY) [ "$#" = 12 ] || exit 2; [ "${#boot}" = 36 ] || exit 2; case "$boot" in *[!0-9a-f-]*) exit 2;; esac;;
 GUARD_TIMING) [ "$#" = 3 ] && [ "$boot" = - ] || exit 2;;
 *) exit 2;;
esac
case "$stage" in /*) ;; *) exit 2;; esac
case "$0" in */*) here=${0%/*};; *) exit 2;; esac
# Validate ALL arguments before reading any evidence.
for arg do [ -n "$arg" ] || exit 2; done
validate_args() {
 while [ "$#" -gt 0 ]; do
  case "$1" in /*) ;; *) return 2;; esac
  case "$2" in /*) ;; *) return 2;; esac
  [ "$3" = 0 ] || return 2
  [ -f "$1" ] && [ ! -L "$1" ] && [ -f "$2" ] && [ ! -L "$2" ] && [ ! -s "$2" ] || return 2
  shift 3
 done
}
validate_args "$@" || exit 2
[ ! -e "$stage" ] && [ ! -L "$stage" ] || exit 2
if diagnostic=$(mkdir -m 700 "$stage" 2>&1; command_rc=$?; printf .; exit "$command_rc"); then :; else exit 2; fi
cleanup() {
 rc=$?; trap - 0 HUP INT TERM
 # Fail closed even when a cleanup command succeeds but emits diagnostics.
 rm -f "$stage/one" "$stage/two" "$stage/three" "$stage/four" "$stage/ascii" "$stage/size" "$stage/normalized" > "$stage/clean" 2>&1 || rc=3
 [ ! -s "$stage/clean" ] || rc=3
 if diagnostic=$(rm -f "$stage/clean" "$stage/err" 2>&1; command_rc=$?; printf .; exit "$command_rc"); then [ "$diagnostic" = . ] || rc=3; else rc=3; fi
 if diagnostic=$(rmdir "$stage" 2>&1; command_rc=$?; printf .; exit "$command_rc"); then [ "$diagnostic" = . ] || rc=3; else rc=3; fi
 exit "$rc"
}
trap cleanup 0
trap 'exit 3' HUP INT TERM
[ "$diagnostic" = . ] || exit 3
i=0
while [ "$#" -gt 0 ]; do
 i=$((i+1))
 case "$i" in 1) name=one;; 2) name=two;; 3) name=three;; 4) name=four;; *) exit 2;; esac
 cap=128
 if [ "$kind" = STATE_ONLY ]; then case "$i" in 1) cap=1024;; 2) cap=4194304;; 3) cap=128;; 4) cap=0;; esac; fi
 wc -c < "$1" > "$stage/size" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] || exit 3
 awk -v cap="$cap" 'NR!=1 || NF!=1 || $1!~/^[0-9]+$/ || $1+0>cap {bad=1} END {exit bad||NR!=1}' "$stage/size" > "$stage/normalized" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] && [ ! -s "$stage/normalized" ] || exit 3
 tr -cd '\011\012\040-\176' < "$1" > "$stage/ascii" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] || exit 3
 cmp -s "$1" "$stage/ascii" > "$stage/normalized" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] && [ ! -s "$stage/normalized" ] || exit 3
 awk '{print}' "$stage/ascii" > "$stage/$name" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] || exit 3
 cmp -s "$stage/ascii" "$stage/$name" > "$stage/normalized" 2> "$stage/err" || exit 3
 [ ! -s "$stage/err" ] && [ ! -s "$stage/normalized" ] || exit 3
 shift 3
done
SNAP_KIND=$kind SNAP_BOOT=$boot; export SNAP_KIND SNAP_BOOT
if [ "$kind" = STATE_ONLY ]; then
 set -- "$stage/one" "$stage/two" "$stage/three" "$stage/four"
else set -- "$stage/one"
fi
awk -f "$here/snapshot.awk" "$@" > "$stage/normalized" 2> "$stage/err" || exit 3
[ ! -s "$stage/err" ] && [ ! -s "$stage/normalized" ] || exit 3
exit 0
