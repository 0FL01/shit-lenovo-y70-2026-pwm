#!/bin/bash
# Recipe bug-hunt fast path (R21 regression, see 06-tools/RECIPE_BUG_HUNT.md).
# Usage: ADB_T=<transport_id> ./recipe_bug_hunt.sh [EVIDENCE_DIR]
# Runs the full known matrix against the live 3-write DC recipe on the bench
# phone, prints a PASS/DEFECT table, auto-heals after each defect, and
# restores the initial sysfs BL at the end.
set -u
T=${ADB_T:-25}
EV=${1:-/tmp/recipe_bug_hunt_$(date +%H%M%S)}
RUNNER=/data/local/tmp/rbd_ddic.sh
export XDG_RUNTIME_DIR=/run/user/1003 ADB_SERVER_SOCKET=localfilesystem:/run/user/1003/legion-y70-adb/adb.sock
mkdir -p "$EV"

adb() { command adb -t "$T" "$@"; }
state() { adb shell "su -c 'timeout -k 3 25 unshare -m /system/bin/sh $RUNNER /data/local/tmp/probe_state.cmd'" 2>/dev/null \
  | grep "^RD" | tr '\n' ' '; }
alive() { state | grep -q "RD 23 0xA9 0x8e" ; }
apply() { adb shell "su -c 'timeout -k 3 25 unshare -m /system/bin/sh $RUNNER /data/local/tmp/recipe_on.cmd'" 2>/dev/null \
  | grep -cE "^W_OK" ; }
bl() { adb shell "su -c 'cat /sys/class/backlight/panel0-backlight/brightness'" | tr -d '\r'; }
fps() { adb shell 'dumpsys display | grep -m1 mActiveRenderFrameRate' 2>/dev/null | grep -oE "[0-9]+\.[0-9]+"; }
report() { # id, expected, status
  printf '%-4s %-28s %-8s %s\n' "$1" "$2" "$3" "$(date +%H:%M:%S)" | tee -a "$EV/hunt.log"; }

BL0=$(bl)
echo "hunt start: BL0=$BL0, evidence=$EV" | tee -a "$EV/hunt.log"
alive && echo "initial: recipe ALIVE" | tee -a "$EV/hunt.log" \
     || { echo "initial: recipe NOT alive - applying" | tee -a "$EV/hunt.log"; apply >/dev/null; }

# T1 brightness sweep
for B in 256 680 1024 2048 3600 6873 1024 512; do
  adb shell "su -c 'echo $B > /sys/class/backlight/panel0-backlight/brightness'" >/dev/null; sleep 1.2
  alive || { report T1 "brightness sweep $B" "DEFECT"; break; }
done
report T1 "brightness sweep" "$(alive && echo PASS || echo DEFECT)"

# T2 adaptive brightness
adb shell 'settings put system screen_brightness_mode 1' >/dev/null; sleep 2
adb shell 'settings put system screen_brightness 80' >/dev/null; sleep 3
report T2 "adaptive brightness" "$(alive && echo PASS || echo DEFECT)"
adb shell 'settings put system screen_brightness_mode 0' >/dev/null; sleep 1

# T3 refresh forcing
for HZ in 60.0 90.0 144.0 120.0; do
  adb shell "settings put system min_refresh_rate $HZ" >/dev/null
  adb shell "settings put system peak_refresh_rate $HZ" >/dev/null; sleep 3.5
  alive || break
done
report T3 "refresh 60/90/144/120" "$(alive && echo PASS || echo DEFECT)"
adb shell 'settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 0' >/dev/null; sleep 2

# T4 screen off/on (known defect -> expect DEFECT then heal)
adb shell 'input keyevent 26'; sleep 3
adb shell 'input keyevent KEYCODE_WAKEUP'; sleep 2.5
if alive; then report T4 "screen off/on" "PASS"; else report T4 "screen off/on" "DEFECT(expected)"; apply >/dev/null; alive && report T4b "heal after screen" "PASS" || report T4b "heal after screen" "FAIL"; fi

# T5 stock Flicker prevention (root-only PUT)
adb shell "su -c 'content call --uri content://com.motorola.android.providers.settings/global --method PUT_global --arg display_dc_mode_enabled --extra value:s:0'" >/dev/null 2>&1; sleep 3
if alive; then report T5 "stock toggle OFF" "PASS"; else report T5 "stock toggle OFF" "DEFECT(expected)"; apply >/dev/null; alive && report T5b "heal after stock" "PASS" || report T5b "heal after stock" "FAIL"; fi

# restore
adb shell "su -c 'echo $BL0 > /sys/class/backlight/panel0-backlight/brightness'" >/dev/null
state | tee -a "$EV/hunt.log"
echo "hunt done: BL restored to $BL0; recipe $(alive && echo ALIVE || echo DEAD)" | tee -a "$EV/hunt.log"
