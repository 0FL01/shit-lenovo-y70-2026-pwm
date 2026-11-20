#!/usr/bin/env python3
"""Build the R39 loss-before-I/O fault fixture offline (stdout, --check, -o NEW_FILE).

Target: /data/adb/legion-r39-guard/guard.sh timeout|disconnect, one of each.
Host brackets each experiment with independent ESD/mount, HWC 0 and R35 page-23
checks at stock BL 1024. Only after R39_WAIT, terminate the one local adb client
for 'disconnect'. Timeout/status alone is not evidence of a host disconnect.
"""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys


R35 = Path(__file__).resolve().parents[1] / 'direct_camera_r35_20261120/build_reader.py'
R35_SHA = '753daaa899b558711fd65a42a9d2b9c77d2037c3bebc130e9cd613168c3e4779'
DIR = '/data/adb/legion-r39-guard'

CHECKS = r'''
qualified() { ready "$1" && stock_off && [ "$(cat "$BL/brightness")" = 1024 ]; }
clear_mount() {
    cat /proc/self/mountinfo | awk -v p="$DBG" '$5 == p { found=1 } END { exit (NR == 0 || found) }'
}
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
'''

FINISH = r'''
finish() {
    trap - EXIT
    trap '' HUP INT TERM PIPE
    fault_rc=$1 esd=unverified unmount=unverified post=unverified
    # Never change a non-stock ESD setting found on admission. Once armed,
    # restore even if isolation was interrupted before its readback succeeded.
    if [ "$armed" = 1 ] && printf 'reg_read\n' > "$ESD" &&
       [ "$(tr -d '\000' < "$ESD")" = reg_read ]; then esd=reg_read; fi
    # Unlike an early return on restore failure, still attempt the unmount.
    if umount "$DBG" && clear_mount; then unmount=verified; fi
    if qualified "$epoch"; then post=verified; fi
    final_rc=$fault_rc
    [ "$esd/$unmount/$post" = reg_read/verified/verified ] || final_rc=7
    # Publish a complete record by hard link, never a partial .result file.
    # The fresh root:0700 reservation is retained, including on SIGKILL.
    tmp=$DIR/$action.once/receipt
    absent "$tmp" && absent "$DIR/$action.result" &&
        printf 'R39_RESULT action=%s epoch=%s isolated=%s rc=%s esd=%s unmount=%s post=%s final_rc=%s\n' \
          "$action" "$epoch" "$isolated" "$fault_rc" "$esd" "$unmount" "$post" "$final_rc" > "$tmp" &&
        ln "$tmp" "$DIR/$action.result" || exit 8
    exit "$final_rc"
}
'''

# Only the child writes to the host's stdout. The supervisor has no success
# print, no reads from the client, and its EXIT cleanup is outside timeout.
WAIT = r'''printf 'R39_WAIT action=%s\n' "$1" || exit 74
exec sleep 20'''


def build():
    raw = R35.read_bytes()
    if sha256(raw).hexdigest() != R35_SHA:
        raise ValueError('review R35 source drift')
    sys.path.insert(0, str(R35.parent))
    import build_reader as base
    s = base.pinned('06-tools/recipe_session.sh', base.SESSION_SHA)
    r = base.pinned('artifacts/direct_camera_r34_20261120/build_probe.py', base.R34_SHA)
    common = s(3, 6) + f'DIR={DIR}\n' + s(10, 12) + s(14, 14) + s(17, 17)
    guards = s(28, 42) + s(49, 66) + CHECKS
    supervisor = common + guards + FINISH + r'''
action=$1 epoch=$2 armed=0 isolated=0
qualified "$epoch" && clear_mount || exit 2
''' + s(124, 124).replace('return 7', 'exit 7') + r'''trap 'finish "$?"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 141' PIPE
[ "$(tr -d '\000' < "$ESD")" = reg_read ] || exit 7
armed=1
''' + s(132, 133).replace('return 7', 'exit 7') + r'''isolated=1
timeout -k 1 4 /system/bin/sh -s -- "$action" <<'R39_WAIT_CHILD'
''' + WAIT + '\nR39_WAIT_CHILD\nexit "$?"\n'
    entry = '#!/system/bin/sh\n' + common + s(20, 26) + guards
    entry += r(136, 139).replace('SELF=$DIR/probe.sh', 'SELF=$DIR/guard.sh') + r(141, 146)
    entry += r'''    qualified "$epoch" && clear_mount || fail 'need fresh stock 1024 without a prior mount'
    action=$1
    absent "$DIR/$action.result" || fail 'result already exists'
''' + r(155, 156) + r'''    mkdir -m 700 "$DIR/$action.once" || fail 'action already reserved; no retry'
    unshare -m /system/bin/sh -s -- "$action" "$epoch" <<'R39_SUPERVISOR'
''' + supervisor + r'''R39_SUPERVISOR
}
[ "$#" -eq 1 ] || fail 'usage: guard.sh timeout|disconnect'
case "$1" in timeout|disconnect) ;; *) fail 'unknown guard action' ;; esac
''' + r(178, 187).replace('@SESSION_SHA@', base.SESSION_SHA)

    # Audit the emitted fixture, including its nested shell. There are no page
    # selectors, register operations, detached workers, or host kill commands.
    for token in ('tx_cmd', 'rx_cmd', '$DSI', '$PAGE', 'select_page', 'read_reg', 'PUT_global', 'setsid', 'adb kill'):
        if token in entry:
            raise ValueError(f'unexpected operation: {token}')
    writes = [line.strip() for line in entry.splitlines() if '> "$ESD"' in line]
    if (writes != ['if [ "$armed" = 1 ] && printf \'reg_read\\n\' > "$ESD" &&',
                   "printf 'esd_sw_sim_success\\n' > \"$ESD\" &&"]
            or entry.count('timeout -k 1 4 ') != 1 or entry.count('R39_WAIT action=') != 1):
        raise ValueError('unexpected ESD isolation/cleanup or child')
    for stage in (entry, supervisor, WAIT):
        subprocess.run(['sh', '-n'], input=stage, text=True, check=True)
    return entry


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    script = build()
    if args.check:
        print('OK: pinned stock/locks and ESD isolation, 3 shells, 4-second timeout, no panel I/O')
    elif args.output:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
