#!/bin/sh
# Synthetic userspace ONLY. This does not dispatch any device/trial operation.
set -u
umask 077
LC_ALL=C; export LC_ALL
[ "$#" = 2 ] || exit 2
W=$1; expected_uid=$2
case "$W" in /*) ;; *) exit 2;; esac
case "$expected_uid" in ''|*[!0-9]*) exit 2;; esac
case "$0" in /*) B=${0%/*};; *) exit 2;; esac
export B W
for tool in sh timeout sleep id sha256sum mkdir rm rmdir cat cmp tr od tail wc stat awk mv; do
 command -v "$tool" >/dev/null 2>&1 || exit 2
done
[ ! -e "$W" ] && [ ! -L "$W" ] || exit 2
uid=$(id -u) || exit 2
[ "$uid" = "$expected_uid" ] || exit 2
# Outer launcher must already have verified trusted manifest and bundle/source.
(cd "$B" && sha256sum -c SHA256SUMS) >/dev/null || exit 2
mkdir -m 700 "$W" || exit 2
TMPDIR=$W; export TMPDIR
# Input mode/owner and trusted parent are launch obligations. Never fix them here.
run() {
 n=$1
 (ulimit -f 32768 || exit 3; timeout -k 1 4 sh "$B/cases/$n.sh" > "$W/$n.stdout" 2> "$W/$n.stderr")
 r=$?
 printf '%s\n' "$r" > "$W/$n.rc" || exit 3
 # Timeout/cancellation uncertainty stops dispatch and never creates completion.
 [ "$r" != 124 ] && [ "$r" != 137 ] || exit 4
}
run arithmetic
run read_eof
run byte_wc
run byte_od
run byte_tr
run byte_tail
run byte_cmp
run noclobber
run override
run fd_empty
run fd_lf
run fd_nul
run metadata_mode
run metadata_links
run owner
run metadata_owner
run bytes_empty
run bytes_lf
run bytes_noLF
run bytes_line32768
run bytes_line32769
run awk_features
run limit_units
run finite_timeout
run capture_write
run capture_write_bad
run capture_rc7
run capture_lf
run capture_nul
run capture_85
run capture_85_bad
run capture_C1
run capture_C1_bad
run interval_valid
run interval_short
run interval_collision
run interval_tail
run state_valid
run state_raw_identity
run state_escape_alias
run state_missing_identity
run snapshot_rc7
run snapshot_lf
run snapshot_nul
run state_owner_lf
run guard0
run guard1
run guard2
run guard3
run guard4
run guard5
run envelope_valid
run envelope_collision
run envelope_bad
run envelope_rc7
run envelope_lf
run envelope_nul
printf "SYNTHETIC_OBSERVATIONS_ONLY\n" > "$W/OBSERVED"
