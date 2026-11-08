#!/bin/sh
# OFFLINE ONLY. Never executes an evidence producer or any device operation.
set -u
LC_ALL=C; export LC_ALL
umask 077
[ "$#" = 6 ] || exit 2
raw=$1; plan=$2; nonce=$3; producer_rc=$4; producer_err=$5; out=$6
# Paths must be absolute, avoiding option/awk assignment interpretation.
for path in "$raw" "$plan" "$producer_err" "$out"; do case "$path" in /*) ;; *) exit 2;; esac; done
case "$out" in */|*'/../'*|*'/./'*) exit 2;; esac
[ "${#nonce}" = 12 ] || exit 2
case "$nonce" in *[!0-9a-f]*) exit 2;; esac
[ "$producer_rc" = 0 ] || exit 2
[ -f "$raw" ] && [ -r "$raw" ] && [ ! -L "$raw" ] || exit 2
[ -f "$plan" ] && [ -r "$plan" ] && [ ! -L "$plan" ] || exit 2
[ -f "$producer_err" ] && [ -r "$producer_err" ] && [ ! -L "$producer_err" ] && [ ! -s "$producer_err" ] || exit 2
[ ! -e "$out" ] && [ ! -L "$out" ] || exit 2
stage=$out.stage
[ ! -e "$stage" ] && [ ! -L "$stage" ] || exit 2
# mkdir failure never authorizes cleanup of a directory we did not create.
mkdir -m 700 "$stage" || exit 2
cleanup() {
 rc=$?; trap - 0 HUP INT TERM
 if [ -d "$stage" ]; then
  for name in section01 section02 section03 section04 section05 section06 section07 section08 section09 section10 section11 section12 section13 section14 section15 section16 bytes err size SUCCESS; do
   rm -f "$stage/$name" || rc=3
  done
  rmdir "$stage" || rc=3
 fi
 exit "$rc"
}
trap cleanup 0
trap 'exit 3' HUP INT TERM
# Check each producer's exit and stderr separately. No pipelines/substitution.
wc -c < "$raw" > "$stage/size" 2> "$stage/err" || exit 3
[ ! -s "$stage/err" ] || exit 3
IFS=' ' read -r size rest < "$stage/size" || exit 3
case "$size" in ''|*[!0-9]*) exit 3;; esac
[ -z "${rest:-}" ] && [ "${#size}" -le 8 ] && [ "$size" -le 25165824 ] || exit 3
P85_RAW_SIZE=$size; export P85_RAW_SIZE
wc -c < "$plan" > "$stage/size" 2> "$stage/err" || exit 3
[ ! -s "$stage/err" ] || exit 3
IFS=' ' read -r size rest < "$stage/size" || exit 3
case "$size" in ''|*[!0-9]*) exit 3;; esac
[ -z "${rest:-}" ] && [ "${#size}" -le 4 ] && [ "$size" -le 976 ] || exit 3
od -An -v -tu1 < "$raw" > "$stage/bytes" 2> "$stage/err" || exit 3
[ ! -s "$stage/err" ] || exit 3
P85_NONCE=$nonce P85_PLAN=$plan P85_STAGE=$stage; export P85_NONCE P85_PLAN P85_STAGE
# Script location, PATH/tool authenticity, stable inputs and exclusive parent are caller obligations.
case "$0" in */*) here=${0%/*};; *) exit 2;; esac
awk -f "$here/decode.awk" "$stage/bytes" > "$stage/size" 2> "$stage/err" || exit 3
[ ! -s "$stage/err" ] && [ ! -s "$stage/size" ] || exit 3
rm "$stage/bytes" "$stage/err" "$stage/size" || exit 3
# Caller guarantees no concurrent destination creation (shared-UID TOCTOU unsolved).
[ ! -e "$out" ] && [ ! -L "$out" ] || exit 3
mv "$stage" "$out" || exit 3
# Mark success only after rename itself reports success. Uncertain rename has no marker.
printf 'P85-OFFLINE-ASCII-ENVELOPE-v1\n' > "$out/SUCCESS" || exit 3
exit 0
