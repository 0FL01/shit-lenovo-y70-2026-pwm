#!/usr/bin/env python3
"""Build R40 offline: probe.py --nonce 12_LOWERCASE_HEX [--check | -o NEW_FILE].

Target: /data/adb/legion-r40/probe.sh ACTION EXPECTED_WAKE (root:0700).
Host verifies HWC0 and ordering, saves stdout/stderr/rc, validates each native
frame before authorizing the next action. No automatic repeats. R40_OK means
I/O and cleanup succeeded, not that a candidate payload was qualified.
"""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DIR = '/data/adb/legion-r40'
SOURCES = {
    'artifacts/direct_camera_r35_20261120/build_reader.py':
        '753daaa899b558711fd65a42a9d2b9c77d2037c3bebc130e9cd613168c3e4779',
    '06-tools/capture_ddic_c1.py': '644fb4a458a00cf6fa9a5fbdf62c269a898862c9f60fbf16eef298aa8db643ce',
    '06-tools/capture_ddic_85.py': 'd25587b8b31ae1f682b1b096727e5471b0df7822fc0a267552f0dd2d3fa7d683',
}

GUARDS = r'''
qualified() {
    ready "$1" && stock_off && [ "$(cat "$BL/brightness")" = 1024 ] &&
    timeout 3 dumpsys display | awk '
      /mActiveSfDisplayMode=/ {
        sub(/^.*mActiveSfDisplayMode=/, ""); sub(/}.*/, ""); rows++
        if (match($0, /peakRefreshRate=[0-9.]+,/) &&
            (p=substr($0,RSTART+16,RLENGTH-17)+0) >= 119.97 && p <= 120.03 &&
            match($0, /vsyncRate=[0-9.]+,/) &&
            (v=substr($0,RSTART+10,RLENGTH-11)+0) >= 119.97 && v <= 120.03) ok++
      } END { exit !(rows == 1 && ok == 1) }'
}
clear_mount() {
    cat /proc/self/mountinfo | awk -v p="$DBG" '$5 == p {found=1} END {exit (NR==0 || found)}'
}
'''

# Android printf may be external. Register the *actual writer*, independently
# for each of the three writes, before exec (which preserves the registered PID).
# Neither an mksh pipeline wrapper nor the debugfs readback cat is the RX task.
WRITER = r'''printf '%s\n' "$$" > "$1/set_event_pid" &&
awk -v pid="$$" 'NF != 1 || $1 != pid {bad=1} END {exit (bad || NR != 1)}' "$1/set_event_pid" &&
printf 1 > "$1/tracing_on" && exec /system/bin/toybox printf '%s' "$3" > "$2"'''

READS = r'''
known() {
    got=$(read_reg "$1" "$2" "$3" | octets "$2") && [ "$got" = "$4" ] ||
        fail "unexpected known response: $1:$3"
}
candidate() {
    # Same R35 TX status gate on both selectors. After an uncertain TX never
    # issue another write. R35's sole recovery is a return after synchronous RX
    # failure with verified selection and a still-ready panel.
    panel_on && printf 1 > "$T/events/$G/enable" &&
        traced_write "$DSI/tx_cmd" "$PAGE 0x02" && tx_ok || return 1
    if ! traced_write "$DSI/rx_cmd" "3 0x06 1 0 1 0 0 1 $1" ||
       ! cat "$DSI/rx_cmd" > "$W/data"; then
        ready "$epoch" && traced_write "$DSI/tx_cmd" "$PAGE 0x00" && tx_ok ||
            printf '%s\n' 'ERROR: page 0 not verified after RX failure' >&2
        return 1
    fi
    panel_on && traced_write "$DSI/tx_cmd" "$PAGE 0x00" && tx_ok
}
{
action=$1 epoch=$2 W=$DIR/$1.once
qualified "$epoch" || exit 2
case "$action" in
    ctrl) known 0x23 1 0xFE 23 && known 0x23 1 0x80 50 &&
          known 0x23 1 0x82 00 && known 0x23 1 0xBA 00 &&
          known 0x00 2 0x52 0400 && printf 'CTRL FE=23 80=50 82=00 BA=00 DBV=0400\n' ;;
    kfe)  known 0x23 1 0xFE 23 && printf 'ANCHOR FE=23\n' ;;
    k80)  known 0x23 1 0x80 50 && printf 'ANCHOR 80=50\n' ;;
    fe)       candidate 0xFE ;;
    a80|b80) candidate 0x80 ;;
    a82|b82) candidate 0x82 ;;
    aba|bba) candidate 0xBA ;;
    *) exit 1 ;;
esac || exit 3
} </dev/null
'''

TRACE = r'''
setup_trace() {
    [ ! -e "$TR/events/$G" ] && mkdir "$T" || return 1
    own_instance=1
    printf 0 > "$T/tracing_on" && printf mono > "$T/trace_clock" &&
        printf 64 > "$T/buffer_size_kb" && [ -w "$T/set_event_pid" ] || return 1
@INSTALL@
    return 0
}
stop_trace() {
    printf 0 > "$T/tracing_on" || bad=1
    if [ -d "$T/events/$G" ]; then printf 0 > "$T/events/$G/enable" || bad=1; fi
}
save_trace() {
    timeout -k 1 3 cat "$T/trace" > "$W/trace" || bad=1
    for e in $added; do
        timeout -k 1 3 grep -E "(^|[[:space:]])$e[[:space:]]" "$TR/kprobe_profile" || bad=1
    done > "$W/profile" || bad=1
}
remove_trace() {
    rmdir "$T" || bad=1
    for e in $added; do printf '%s\n' "-:$G/$e" >> "$TR/kprobe_events" || bad=1; done
    [ ! -e "$T" ] && [ ! -e "$TR/events/$G" ] || bad=1
}
emit_evidence() {
    printf 'NONCE %s\n' "$nonce" || return 1
    if [ -f "$W/data" ]; then
        awk '{$1=$1; print "DATA " tolower($0)}' "$W/data" || return 1
    fi
    printf 'TRACE_BEGIN\n' && cat "$W/trace" && printf 'TRACE_END\nPROFILE_BEGIN\n' &&
        cat "$W/profile" && printf 'PROFILE_END\n'
}
'''

SUPERVISE = r'''
action=$1 epoch=$2 W=$DIR/$1.once
mounted=0 armed=0 own_instance=0 added='' bad=0 interrupted=0
finish() {
    rc=$1
    trap - EXIT
    trap '' HUP INT TERM PIPE
    if [ "$own_instance" = 1 ]; then stop_trace; fi
    if [ "$armed" = 1 ]; then
        printf 'reg_read\n' > "$ESD" && [ "$(tr -d '\000' < "$ESD")" = reg_read ] || bad=1
    fi
    if [ "$mounted" = 1 ]; then umount "$DBG" && clear_mount || bad=1; fi
    if [ "$own_instance" = 1 ]; then
        save_trace
        remove_trace
        # Evidence is retained under the reservation even if the client is lost.
        emit_evidence || bad=1
    fi
    [ "$bad" = 0 ] || { printf '%s\n' 'RECOVERY_REQUIRED' >&2; exit 7; }
    [ "$interrupted" = 0 ] || exit 30
    exit "$rc"
}
trap 'finish "$?"' EXIT
# Do not interrupt the resource acquisition / ownership-flag pairs.
trap 'interrupted=1' HUP INT TERM PIPE
qualified "$epoch" && clear_mount || exit 2
mount -o rprivate none / && mount -t debugfs -o nosuid,nodev,noexec debugfs "$DBG" || exit 7
mounted=1
[ -w "$DSI/tx_cmd" ] && [ -w "$DSI/rx_cmd" ] &&
    [ "$(tr -d '\000' < "$ESD")" = reg_read ] || exit 7
case "$action" in ctrl|kfe|k80) ;; *) setup_trace || exit 7 ;; esac
[ "$interrupted" = 0 ] || exit 30
armed=1
printf 'esd_sw_sim_success\n' > "$ESD" &&
    [ "$(tr -d '\000' < "$ESD")" = esd_sw_sim_success ] || exit 7
[ "$interrupted" = 0 ] || exit 30
timeout -k 3 25 /system/bin/sh -s -- "$action" "$epoch" <<'R40_IO'
'''


def build(nonce):
    if not re.fullmatch('[a-f0-9]{12}', nonce):
        raise ValueError('nonce must be exactly 12 lowercase hex digits')
    for path, digest in SOURCES.items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f'review source drift: {path}')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT / 'artifacts/direct_camera_r35_20261120'), str(ROOT / '06-tools')]
    import build_reader as base
    import capture_ddic_85 as framing

    s = base.pinned('06-tools/recipe_session.sh', base.SESSION_SHA)
    r = base.pinned('artifacts/direct_camera_r34_20261120/build_probe.py', base.R34_SHA)
    _, specs = framing.probe_specs(nonce)
    group = 'r40_' + nonce
    install = []
    for name, (kind, fields) in specs.items():
        spec = shlex.quote(f'{kind}:{group}/{name} {fields}')
        install += [f'    printf \'%s\\n\' {spec} >> "$TR/kprobe_events" || return 1',
                    f'    added="$added {name}"']
    common = s(3, 6) + f'DIR={DIR}\n' + s(10, 17)
    guards = s(28, 42) + s(49, 66) + GUARDS
    tracevars = f'nonce={nonce}\nTR=/sys/kernel/tracing\nG={group}\nT=$TR/instances/$G\n'
    octets = base.IO[base.IO.index('octets()'):base.IO.index('fingerprint()')]
    writer = 'traced_write() { /system/bin/sh -c ' + shlex.quote(WRITER) + ' r40 "$T" "$1" "$2"; }\n'
    io = common + guards + tracevars + s(68, 86) + octets + writer + READS
    supervisor = (common + guards + tracevars + TRACE.replace('@INSTALL@', '\n'.join(install)) +
                  SUPERVISE + io + 'R40_IO\nexit "$?"\n')
    # Reserve before identity/state/debugfs/trace access, after absolute path,
    # root-owned staging, allowlist and session flock checks. Never delete it.
    entry = ('#!/system/bin/sh\n' + common + s(20, 26) + guards + r(136, 139) + r(141, 144) + r'''
    case "$1" in ctrl|kfe|k80) ;; *) mkdir -m 700 "$DIR/$1.once" || fail 'action already reserved; no retry' ;; esac
''' + r(145, 145) + r'''    epoch=$2
    qualified "$epoch" && clear_mount || fail 'wake/panel/stock/brightness/mode mismatch or existing mount'
''' + r(155, 156) + r'''    unshare -m /system/bin/sh -s -- "$1" "$epoch" <<'R40_SUPERVISOR'
''' + supervisor + r'''R40_SUPERVISOR
    rc=$?
    [ "$rc" = 0 ] || return "$rc"
    qualified "$epoch" && clear_mount || fail 'state or mount changed at completion'
    printf 'R40_OK action=%s epoch=%s page=0 esd=reg_read\n' "$1" "$epoch"
}
[ "$#" = 2 ] || fail 'usage: probe.sh ACTION EXPECTED_WAKE'
case "$1" in ctrl|kfe|k80|fe|a80|b80|a82|b82|aba|bba) ;; *) fail 'unknown action' ;; esac
case "$2" in ''|*[!0-9]*) fail 'expected numeric wake epoch' ;; esac
''' + r(178, 187).replace('@SESSION_SHA@', base.SESSION_SHA))

    for stage in (WRITER, io, supervisor, entry):
        subprocess.run(['sh', '-n'], input=stage, text=True, check=True)
    if (re.findall(r'(?m)^\s*([\w|]+)\) +candidate (0x\w+)', io) !=
            [('fe', '0xFE'), ('a80|b80', '0x80'), ('a82|b82', '0x82'), ('aba|bba', '0xBA')] or
            re.findall(r'known (0x\w+ [12] 0x\w+ \w+)', io) !=
            ['0x23 1 0xFE 23', '0x23 1 0x80 50', '0x23 1 0x82 00', '0x23 1 0xBA 00',
             '0x00 2 0x52 0400', '0x23 1 0xFE 23', '0x23 1 0x80 50'] or
            entry.count('traced_write "$DSI/rx_cmd" "3 0x06 1 0 1 0 0 1 $1"') != 1):
        raise ValueError('unexpected reader dispatch')
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nonce', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = parser.parse_args()
    script = build(args.nonce)
    if args.check:
        print('OK: pinned sources, shell stages, fixed controls and 7 one-shot MRPS3 actions')
    elif args.output:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
