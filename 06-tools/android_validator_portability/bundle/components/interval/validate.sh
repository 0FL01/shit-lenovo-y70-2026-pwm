#!/bin/sh
# Offline decoder. Scratch ownership is not evidence ownership or freshness.
set -eu
export LC_ALL=C
[ "$#" -eq 7 ] || exit 2
op=$1; begin=$2; end=$3; ref=$4; nonce=$5; log=$6
[ "$7" = OFFLINE ] || exit 2
case "$op" in read|quiet|dispatch|guard) ;; *) exit 2;; esac
case "$begin" in ''|*[!A-Za-z0-9_]*) exit 2;; esac
[ "${#begin}" -ge 8 ] && [ "${#begin}" -le 180 ] || exit 2
if [ "$op" = guard ]; then
    [ "$end" = - ] || exit 2
else
    case "$end" in ''|*[!A-Za-z0-9_]*) exit 2;; esac
    [ "${#end}" -ge 8 ] && [ "${#end}" -le 180 ] || exit 2
    case "$begin" in *"$end"*) exit 2;; esac
    case "$end" in *"$begin"*) exit 2;; esac
fi
case "$ref" in 120|1) ;; *) exit 2;; esac
if [ "$nonce" != - ]; then
    case "$nonce" in ''|*[!0-9a-f]*) exit 2;; esac
    [ "${#nonce}" -eq 12 ] || exit 2
fi
case "$op" in dispatch|guard) [ "$ref" = 120 ] && [ "$nonce" != - ] || exit 2;; esac
[ -f "$log" ] && [ -r "$log" ] || exit 2
case "$0" in */*) here=${0%/*};; *) here=.;; esac
umask 077
# Atomically create a bounded private directory; never adopt an existing path.
work=${TMPDIR:-/tmp}/pwm-interval-$$
mkdir -m 700 "$work" || exit 1
cleanup() {
    rm -f "$work/err" "$work/size" "$work/last" "$work/byte" "$work/clean" "$work/count" "$work/result" && rmdir "$work"
}
trap 'rc=$?; trap - 0; if ! cleanup; then rc=1; fi; exit "$rc"' 0
trap 'exit 1' 1 2 3 15
# POSIX512-byte units: bound every producer stdout/stderr file to16MiB.
ulimit -f 32768 || exit 1
produce() {
    output=$1; shift
    if "$@" > "$output" 2> "$work/err"; then
        [ ! -s "$work/err" ] || exit 1
    else
        exit 1
    fi
}
# Builtin read checks one complete record, one field, no trailing bytes.
number() {
    value=; extra=; trailing=
    { read -r value extra && [ -z "$extra" ] && ! IFS= read -r trailing && [ -z "$trailing" ]; } < "$1" || exit 1
    case "$value" in ''|*[!0-9]*) exit 1;; esac
    [ "${#value}" -le 9 ] || exit 1
}
produce "$work/size" wc -c < "$log"
number "$work/size"; size=$value
[ "$size" -gt 0 ] && [ "$size" -le 16777216 ] || exit 1
produce "$work/last" tail -c 1 < "$log"
produce "$work/byte" od -An -tu1 < "$work/last"
number "$work/byte"; [ "$value" = 10 ] || exit 1
produce "$work/clean" tr -cd '\11\12\40-\176' < "$log"
produce "$work/count" wc -c < "$work/clean"
number "$work/count"; [ "$value" -eq "$size" ] || exit 1
produce "$work/result" awk -v op="$op" -v begin="$begin" -v end="$end" -v ref="$ref" -v nonce="$nonce" -f "$here/interval.awk" < "$log"
verdict=; trailing=
{ IFS= read -r verdict && ! IFS= read -r trailing && [ -z "$trailing" ]; } < "$work/result" || exit 1
[ "$verdict" = 'ACCEPT offline interval semantics only' ] || exit 1
cleanup || exit 1
trap - 0 1 2 3 15
printf '%s\n' "$verdict"
