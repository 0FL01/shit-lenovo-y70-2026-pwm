#!/system/bin/sh
# Session-only 0x8e applier. See RECIPE_SESSION.md before using on the target.
set -u -o pipefail
umask 077
PATH=/system/bin:/system/xbin
export PATH

DIR=/data/adb/legion-dc-session
SELF=$DIR/recipe_session.sh
DRM=/sys/class/drm/card0-DSI-1
BL=/sys/class/backlight/panel0-backlight
DBG=$DIR/debugfs
DSI=$DBG/dri/9800000.qcom,mdss_mdp/DSI-1
ESD=$DBG/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode
PAGE='0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5'

fail() { printf '%s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*" > "$DIR/state.new" && mv "$DIR/state.new" "$DIR/state"; }

identify() {
    [ "$(getprop ro.boot.hardware.sku)" = XT2611-1 ] &&
    [ "$(getprop ro.build.display.id)" = W3WWS36.65-64-4-1 ] &&
    [ "$(cat "$DRM/panelName")" = boe_ili97701A_682_1440x3168_dsc_cmd_v4 ] &&
    [ "$(cat "$DRM/panelId")" = 0x00000000000000d2 ] &&
    printf '%s\n' '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804  /vendor/lib/modules/msm_drm.ko' | sha256sum -c -s
}

# A wake timestamp also detects an OFF/ON between polls. Missing or ambiguous
# power data is neither permission to write nor evidence of a transition.
power_state() {
    timeout 3 dumpsys power | awk '
        $1 ~ /^mWakefulness=(Awake|Asleep|Dozing|Dreaming)$/ { sub(/^.*=/, "", $1); state=$1; states++ }
        $1 ~ /^mWakefulnessChanging=(true|false)$/ { sub(/^.*=/, "", $1); changing=$1; flags++ }
        $1 ~ /^mLastWakeTime=[0-9]+$/ { sub(/^.*=/, "", $1); epoch=$1; seen++ }
        END { if (states == 1 && flags == 1 && seen == 1) print epoch ":" state ":" changing; else exit 1 }'
}

awake_epoch() {
    snapshot=$(power_state) || return 1
    case "$snapshot" in *:Awake:false) printf '%s\n' "${snapshot%%:*}" ;; *) return 1 ;; esac
}

transitioned() {
    snapshot=$(power_state) || return 1
    [ "${snapshot%%:*}" != "$1" ] && return 0
    case "$snapshot" in *:Asleep:*|*:Dozing:*) return 0 ;; *) return 1 ;; esac
}

panel_on() {
    [ "$(cat "$DRM/enabled")" = enabled ] && [ "$(cat "$DRM/dpms")" = On ] &&
    [ "$(cat "$BL/bl_power")" = 0 ]
}

ready() {
    panel_on && [ "$(awake_epoch)" = "$1" ] || return 1
    # Only qualify the observed single-display topology; exclude DOZE and AOD.
    timeout 3 dumpsys display | awk '
        $1 ~ /^mCommittedState=/ { committed++; if ($1 == "mCommittedState=ON") on++ }
        END { exit !(committed == 1 && on == 1) }'
}

stock_off() {
    [ "$(cat "$DRM/panelDC")" = 0 ] &&
    [ "$(timeout 3 content call --uri content://com.motorola.android.providers.settings/global \
        --method GET_global --arg display_dc_mode_enabled)" = 'Result: Bundle[{value=0}]' ]
}

tx() {
    # The pinned driver returns the accepted byte count even on DSI failure.
    printf '%s' "$1" > "$DSI/tx_cmd" &&
        [ "$(cat "$DSI/tx_cmd")" = 'last_cmd_tx_sts:0x1' ] || {
        printf '%s\n' 'ERROR: DSI TX not acknowledged; no further packets in this transaction' >&2
        return 1
    }
}

select_page() { tx "$PAGE $1"; }
read_reg() {
    panel_on && select_page "$1" || return 1
    if printf '%s' "$2 0x06 1 0 1 0 0 1 $3" > "$DSI/rx_cmd"; then
        value=$(cat "$DSI/rx_cmd") || return 1
        select_page 0x00 || return 1
        printf '%s\n' "$value" | awk '{$1=$1; print tolower($0)}'
    else
        return 1
    fi
}

write_reg() {
    panel_on && select_page "$1" && panel_on &&
    tx "0x39 0 0 0 0 0 2 $2 $3" &&
    select_page 0x00 && [ "$(read_reg "$1" 1 "$2")" = "$3" ]
}

apply_core() {
    write_reg 0x23 0xA9 "$1" && write_reg 0x24 0x9D "$2" && write_reg 0x23 0x80 "$3"
}

cleanup() {
    trap - EXIT
    trap '' HUP INT TERM
    # ESD is owned by this supervisor, not by the timed DSI child. Do not
    # issue a blind page select here if the child's last TX was uncertain.
    if ! printf 'reg_read\n' > "$ESD" || [ "$(tr -d '\000' < "$ESD")" != reg_read ]; then
        printf '%s\n' 'ERROR: ESD restoration not verified' >&2
        return 7
    fi
    umount "$DBG" || return 7
}

transaction() {
    # Only called from run_txn under the worker lock, in a private mount namespace.
    action=$1 epoch=$2
    case "$action" in apply|restore) ;; *) return 1 ;; esac
    ready "$epoch" || return 2
    stock_off || return 4
    mount -o rprivate none / && mount -t debugfs -o nosuid,nodev,noexec debugfs "$DBG" || return 7
    if [ ! -w "$DSI/tx_cmd" ] || [ ! -w "$DSI/rx_cmd" ] ||
       [ "$(tr -d '\000' < "$ESD")" != reg_read ]; then
        umount "$DBG"
        return 7
    fi
    trap 'rc=$?; cleanup || rc=7; exit "$rc"' EXIT
    trap 'exit 30' HUP INT TERM
    printf 'esd_sw_sim_success\n' > "$ESD" &&
        [ "$(tr -d '\000' < "$ESD")" = esd_sw_sim_success ] || return 7
    timeout -k 3 15 /system/bin/sh "$SELF" _io "$action" "$epoch"
    rc=$?
    cleanup || rc=7
    return "$rc"
}

panel_io() {
    action=$1 epoch=$2
    ready "$epoch" || return 2
    stock_off || return 4
    a9=$(read_reg 0x23 1 0xA9) && d9=$(read_reg 0x24 1 0x9D) &&
        r80=$(read_reg 0x23 1 0x80) && c1=$(read_reg 0x23 3 0xC1) || return 1
    case "$action/$a9/$d9/$r80/$c1" in
        'restore/0x8e/0x8e/0x90/0x00 0x00 0x10') ;;
        'apply/0x0e/0x0e/0x50/'*)
            # C1 varies with DBV even with the stock core.
            case "$c1" in 0x[0-9a-f][0-9a-f]' '0x[0-9a-f][0-9a-f]' '0x[0-9a-f][0-9a-f]) ;; *) return 5 ;; esac ;;
        *) return 5 ;; # Unknown / experimental configuration: do not overwrite.
    esac
    ready "$epoch" || return 2
    stock_off || return 4
    if [ "$action" = restore ]; then
        apply_core 0x0e 0x0e 0x50
    else
        apply_core 0x8e 0x8e 0x90 && [ "$(read_reg 0x23 3 0xC1)" = '0x00 0x00 0x10' ]
    fi
}

run_txn() {
    unshare -m /system/bin/sh "$SELF" _txn "$@"
    rc=$?
    # The supervisor already verified ESD cleanup on these return codes.
    # A timed-out child, a bad entry, or failed cleanup is never auto-retried.
    case "$rc" in
        0|1|2) if transitioned "$2"; then return 3; fi ;;
    esac
    if [ "$rc" = 0 ] && ! ready "$2"; then return 1; fi
    return "$rc"
}

watch() {
    note waiting-for-next-wake
    candidate= owned= last=$1
    while [ ! -e "$DIR/stop" ]; do
        epoch=$(awake_epoch) || epoch=
        if [ -n "$epoch" ] && [ "$epoch" != "$last" ] && [ "$epoch" = "$candidate" ] && ready "$epoch"; then
            [ ! -e "$DIR/stop" ] || break
            if run_txn apply "$epoch"; then
                last=$epoch
                owned=$epoch
                note "active: verified wake=$epoch"
                printf 'applied and read back wake=%s\n' "$epoch"
            else
                case "$?" in
                    2) ;; # Not ready, no payload issued.
                    3) last=$epoch; owned=; note waiting-for-next-wake ;;
                    4) note 'error: stock anti-flicker must be OFF; stopped'; return 1 ;;
                    5) note 'error: not a fresh stock core; stopped without payload'; return 1 ;;
                    *) note 'error: apply/readback/cleanup failed; stopped'; return 1 ;;
                esac
            fi
        fi
        candidate=$epoch
        sleep 1
    done
    if [ -z "$owned" ] || ! ready "$owned"; then
        note 'stopped: no owned ready wake; no DDIC write'
        return 0
    fi
    if run_txn restore "$owned"; then
        note 'stopped: stock registers verified'
    elif [ "$?" = 3 ]; then
        note 'stopped: screen transitioned; stock restore not verified'
    else
        note 'error: stopped, stock restore not verified'
        return 1
    fi
}

start_session() {
    flock -n 8 || fail 'another control command is running'
    flock -n 9 || fail 'session already running'
    identify || fail 'target/build/module/panel mismatch'
    stock_off || fail 'stock anti-flicker must be OFF'
    snapshot=$(power_state) || fail 'power state not available'
    mkdir -p "$DBG" && rm -f "$DIR/stop" && note starting || exit 1
    setsid /system/bin/sh "$SELF" _watch "${snapshot%%:*}" 8>&- </dev/null > "$DIR/log" 2>&1 &
}

status_session() {
    if flock -n 9; then echo inactive; else echo running; fi
    if [ -f "$DIR/state" ]; then cat "$DIR/state"; fi
}

stop_session() {
    flock -n 8 || fail 'another control command is running'
    : > "$DIR/stop" || exit 1
    if flock -n 9; then
        echo 'inactive: no DDIC write; normal screen wake resets the recipe'
        return 0
    else
        timeout 45 flock 9 || fail 'stop requested, worker has not yet stopped'
    fi
    cat "$DIR/state"
    case "$(cat "$DIR/state")" in stopped:*) ;; *) exit 1 ;; esac
}

[ "$(id -u)" = 0 ] || fail 'root required'
[ "$(stat -c '%u:%a' "$DIR")" = 0:700 ] && [ "$(stat -c '%u:%a' "$SELF")" = 0:700 ] ||
    fail 'expected root-owned installation (0700)'

case "${1:-}" in
    # mksh marks FDs from a standalone `exec N>` close-on-exec. Bind them to
    # function calls so toybox flock and the detached worker inherit them.
    start) start_session 8> "$DIR/control.lock" 9> "$DIR/worker.lock" ;;
    status) status_session 9> "$DIR/worker.lock" ;;
    stop) stop_session 8> "$DIR/control.lock" 9> "$DIR/worker.lock" ;;
    _watch) watch "$2" ;;
    _txn) transaction "$2" "$3" ;;
    _io) panel_io "$2" "$3" ;;
    *) fail 'usage: recipe_session.sh start|status|stop' ;;
esac
