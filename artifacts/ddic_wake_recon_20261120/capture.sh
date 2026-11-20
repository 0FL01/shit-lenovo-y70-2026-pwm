#!/system/bin/sh
# Run once on the identified XT2611-1, as root, under a device-side timeout.
# Stdout is private bench evidence. No direct DDIC/debugfs panel writes.
set -eu -o pipefail
T=/sys/kernel/tracing
G=legion_wake_recon
I=$T/instances/$G
P=$T/kprobe_events
S=/data/adb/legion-dc-session/recipe_session.sh
made=0 stop_requested=0 slept=0 aod_changed=0 probes=

cleanup() {
    rc=$? restore_rc=0
    trap - EXIT
    trap '' HUP INT TERM
    if [ "$made" = 1 ]; then
        printf '0\n' > "$I/tracing_on" || restore_rc=1
        rmdir "$I" || restore_rc=1
        for p in $probes; do printf '%s\n' "-:$G/$p" >> "$P" || restore_rc=1; done
        [ ! -e "$I" ] && ! grep -Fq "$G/" "$P" || restore_rc=1
    fi
    if [ "$aod_changed" = 1 ]; then
        if [ "$aod0" = null ]; then settings delete secure doze_always_on >/dev/null || restore_rc=1
        else settings put secure doze_always_on "$aod0" || restore_rc=1; fi
        [ "$(settings get secure doze_always_on)" = "$aod0" ] || restore_rc=1
    fi
    if [ "$stop_requested" = 1 ]; then
        # Restore the prior session only after our probes are removed.
        if [ "$restore_rc" = 0 ]; then
            status=$("$S" status) || restore_rc=1
            if printf '%s\n' "$status" | grep -Fxq inactive; then
                input keyevent KEYCODE_SLEEP && sleep 2 &&
                    [ "$(display_state)" = mCommittedState=OFF ] && "$S" start || restore_rc=1
            fi
        fi
        input keyevent KEYCODE_WAKEUP || restore_rc=1
        if [ "$restore_rc" = 0 ]; then
            sleep 7
            status=$("$S" status) || restore_rc=1
            printf '%s\n' "$status" >&2
            printf '%s\n' "$status" | grep -Fxq running || restore_rc=1
            printf '%s\n' "$status" | grep -q '^active: verified wake=' || restore_rc=1
        fi
    elif [ "$slept" = 1 ]; then
        input keyevent KEYCODE_WAKEUP || restore_rc=1
    fi
    printf 'CLEANUP rc=%s\n' "$restore_rc"
    [ "$restore_rc" = 0 ] || rc=1
    exit "$rc"
}

add() {
    printf '%s\n' "$2" >> "$P"
    probes="$1 $probes"
    printf '1\n' > "$I/events/$G/$1/enable"
}

mark() { printf '%s\n' "$*" > "$I/trace_marker"; }
display_state() {
    dumpsys display | awk '$1 ~ /^mCommittedState=/ { print $1; count++ } END { exit !(count == 1) }'
}
await_state() {
    for try in 1 2 3 4 5 6 7 8; do
        s=$(display_state) || return 1
        for wanted in "$@"; do
            if [ "$s" = "mCommittedState=$wanted" ]; then mark "observed $s"; return 0; fi
        done
        sleep 1
    done
    mark "not-observed expected=$* last=$s"
    return 1
}

[ "$(getprop ro.boot.hardware.sku)" = XT2611-1 ]
[ "$(getprop ro.build.display.id)" = W3WWS36.65-64-4-1 ]
[ "$(getenforce)" = Enforcing ]
printf '%s\n' '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804  /vendor/lib/modules/msm_drm.ko' | sha256sum -c -s
printf '%s\n' 'f3eee5b9da97f88eba5b5fbccb3e77090ee101cae466fb908f0b825de109e317  /vendor/lib/modules/panel_event_notifier.ko' | sha256sum -c -s
[ "$(cat /sys/class/drm/card0-DSI-1/panelDC)" = 0 ]
[ "$(content call --uri content://com.motorola.android.providers.settings/global --method GET_global --arg display_dc_mode_enabled)" = 'Result: Bundle[{value=0}]' ]
[ "$(dumpsys deviceidle get screen)" = true ]
status=$("$S" status)
printf '%s\n' "$status" | grep -Fxq running
printf '%s\n' "$status" | grep -q '^active: verified wake='
[ ! -e "$I" ] && ! grep -Fq "$G/" "$P"
aod0=$(settings get secure doze_always_on)
[ "$aod0" = null ] || [ "$aod0" = 0 ]
trap cleanup EXIT
trap 'exit 30' HUP INT TERM

mkdir "$I"
made=1
printf '0\n' > "$I/tracing_on"
printf 'mono\n' > "$I/trace_clock"
printf '256\n' > "$I/buffer_size_kb"
# No pointer/address fields in output. Decoder uses only bytes within tx_len.
add wire 'p:legion_wake_recon/wire msm_drm:dsi_host_transfer_sub type=+1($arg2):x8 len=+8($arg2):u64 op=+0(+16($arg2)):x8 one=+1(+16($arg2)):x8 two=+2(+16($arg2)):x8'
add wire_ret 'r:legion_wake_recon/wire_ret msm_drm:dsi_host_transfer_sub rc=$retval:s32'
add enable 'p:legion_wake_recon/enable msm_drm:dsi_panel_enable'
add post 'p:legion_wake_recon/post msm_drm:dsi_panel_post_enable'
add nolp 'p:legion_wake_recon/nolp msm_drm:dsi_panel_set_nolp'
add param 'p:legion_wake_recon/param msm_drm:dsi_panel_send_param_cmd id=+0($arg2):u32 request=+8($arg2):u32'
add param_ret 'r:legion_wake_recon/param_ret msm_drm:dsi_panel_send_param_cmd rc=$retval:s32'
add bl 'p:legion_wake_recon/bl msm_drm:dsi_display_set_backlight level=$arg3:u32'
add notify 'p:legion_wake_recon/notify panel_event_notifier:panel_event_notification_trigger tag=$arg1:u32 event=+0($arg2):u32 early=+12($arg2):u8'

slept=1
input keyevent KEYCODE_SLEEP
sleep 3
[ "$(dumpsys deviceidle get screen)" = false ]
[ "$(display_state)" = mCommittedState=OFF ]
stop_requested=1
"$S" stop | grep -Fx 'stopped: no owned ready wake; no DDIC write'
"$S" status | grep -Fx inactive
printf '1\n' > "$I/tracing_on"
for round in 1 2; do
    await_state OFF
    mark "full-wake-$round begin"
    input keyevent KEYCODE_WAKEUP
    await_state ON
    sleep 2
    mark "full-wake-$round end"
    if [ "$round" = 1 ]; then input keyevent KEYCODE_SLEEP; sleep 3; fi
done

aod_changed=1
settings put secure doze_always_on 1
[ "$(settings get secure doze_always_on)" = 1 ]
sleep 2
mark 'aod setup'
input keyevent KEYCODE_POWER
if await_state DOZE DOZE_SUSPEND; then
    mark 'aod-wake begin'
    input keyevent KEYCODE_WAKEUP
    await_state ON
    sleep 2
    mark 'aod-wake end'
else
    mark 'aod not qualified'
fi

printf '0\n' > "$I/tracing_on"
printf '%s\n' TRACE_BEGIN
cat "$I/trace"
printf '%s\n' TRACE_END
grep -E 'overrun|dropped' "$I"/per_cpu/cpu*/stats | awk -F: '{print $(NF-1) ":" $NF}'
# kprobe_profile prints bare event names, not their group. Pair trace events
# independently; these return counters are supplemental if names are unique.
awk '$1 == "wire_ret" || $1 == "param_ret" { print "kprobe_profile:", $0 }' "$T/kprobe_profile"
