#!/system/bin/sh
# Only the target-local owner performs transitions. Requests from the host are
# files in the private staging directory, not more panel writes. No boot hook.
set -eu
umask 077
d=/data/adb/legion-r49-probe
epoch=$1
case "$epoch" in ''|*[!0-9]*) exit 2;; esac
[ "$(id -u)" = 0 ] && [ "$0" = "$d/lease.sh" ] && [ "$(stat -c '%u:%a' "$d")" = 0:700 ]
mkdir -m700 "$d/lease.once"
s=$d/lease.once
now(){ read -r t rest < /proc/uptime; printf '%s\n' "${t%%.*}"; }
probe(){ "$d/probe.sh" "$1" "$epoch" > "$s/$1.log" 2>&1 && grep -qx "R49_OK action=$1 epoch=$epoch page=0 esd=reg_read" "$s/$1.log"; }
wait_request(){
    # The deadline is fixed before announcing this phase. Never refreshed by a host read.
    phase=$1; due=$2; key=$3; echo "$due" > "$s/$phase.due"; echo "READY $phase at=$(now) due=$due"
    while [ "$(now)" -lt "$due" ]; do
        if [ -f "$s/$key" ] && [ "$(cat "$s/$key")" = "$epoch" ]; then echo "CLOSE $phase request at=$(now)"; return 0; fi
        sleep .25
    done
    echo "CLOSE $phase deadline at=$(now)"; return 1
}
finish(){
    rc=$?; trap - EXIT; if [ "$rc" != 0 ]; then
        echo "HOLD rc=$rc at=$(now); no automatic retry"; touch "$s/hold"; input keyevent KEYCODE_SLEEP || :
    fi
    exit "$rc"
}
trap finish EXIT
probe enter
# Exercise the actual deadline branch and read back the existing A without
# spending either 9E write. B cannot start without a later host gate.
if wait_request DRY "$(($(now)+5))" unused; then exit 5; fi
probe dry-revert; echo DRY_RETURN_VERIFIED
if wait_request A "$(($(now)+290))" go && [ ! -e "$s/abort" ]; then
    due_b=$(($(now)+165)); probe candidate
    wait_request B "$due_b" return || :
    probe revert
    wait_request R "$(($(now)+165))" finish || :
fi
probe stock; probe stock-check; echo "STOCK_VERIFIED at=$(now)"; touch "$s/done"
