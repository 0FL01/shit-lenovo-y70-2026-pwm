#!/usr/bin/env python3
"""Build the temporary R35 stock reader offline: stdout, --check, or -o NEW_FILE.

Target (root, directory and script 0700):
    /data/adb/legion-r35-read/probe.sh 3600
One argument: an expected brightness, never a brightness setter or address.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SESSION_SHA = '156868ca536a1a8ccf95183cc3dbc46fbfc112ed12df70cc39c958ce89cb9bd9'
R34_SHA = 'd0e6b490195faf2f3e9e20c8ad35579a19959b386567e8770fe50e709235b2b2'


def pinned(path, digest):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f'review source slices after drift: {path}')
    lines = raw.decode('ascii').splitlines(keepends=True)
    return lambda first, last: ''.join(lines[first - 1:last])


GUARDS = r'''
dbv_hex() {
    case "$1" in 1024|3600|3601|4096) printf '%04x' "$1" ;; *) return 1 ;; esac
}
qualified() { ready "$2" && stock_off && [ "$(cat "$BL/brightness")" = "$1" ]; }
'''

IO = r'''
# read_reg returns one normalized driver response. Reject extra/missing bytes,
# status text and multiple records; emit only hex digits. pipefail propagates RX/TX errors.
octets() {
    awk -v n="$1" '
        NR != 1 || NF != n { bad=1 }
        { for (i=1; i<=NF; i++) {
            if ($i !~ /^0x[0-9a-f][0-9a-f]$/) bad=1
            hex=hex substr($i,3)
        } }
        END { if (bad || NR != 1) exit 1; print hex }'
}
fingerprint() {
    fe=$(read_reg 0x23 1 0xFE | octets 1) && [ "$fe" = 23 ] &&
    r80=$(read_reg 0x23 1 0x80 | octets 1) && [ "$r80" = 50 ] &&
    r82=$(read_reg 0x23 1 0x82 | octets 1) && [ "$r82" = 00 ] &&
    ba=$(read_reg 0x23 1 0xBA | octets 1) && [ "$ba" = 00 ]
}

# The shell reads the stage from a heredoc; its utilities get no script input.
{
bl=$1 epoch=$2
expected=$(dbv_hex "$bl") && qualified "$bl" "$epoch" || exit 2
fingerprint && fingerprint || fail 'stock page fingerprint failed'
a9=$(read_reg 0x23 1 0xA9 | octets 1) && [ "$a9" = 0e ] || fail 'stock A9 failed'
a4=$(read_reg 0x23 1 0xA4 | octets 1) &&
ad=$(read_reg 0x23 1 0xAD | octets 1) &&
b4=$(read_reg 0x23 1 0xB4 | octets 1) &&
c1=$(read_reg 0x23 3 0xC1 | octets 3) &&
c2=$(read_reg 0x23 3 0xC2 | octets 3) || fail 'stock register read failed'
dbv=$(read_reg 0x00 2 0x52 | octets 2) && [ "$dbv" = "$expected" ] || fail 'stock DBV failed'
# 00:FE in S1-S4 is a long40 prefix, not a qualified 1-byte request.
# page=0 denotes the final read_reg return selector with native TX status.
qualified "$bl" "$epoch" || exit 2
printf 'FE=%s sig=%s%s%s A4=%s AD=%s B4=%s A9=%s C1=%s C2=%s DBV=%s\n' \
    "$fe" "$r80" "$r82" "$ba" "$a4" "$ad" "$b4" "$a9" "$c1" "$c2" "$dbv"
} </dev/null
'''


def build():
    s = pinned('06-tools/recipe_session.sh', SESSION_SHA)
    r = pinned('artifacts/direct_camera_r34_20261120/build_probe.py', R34_SHA)
    common = s(3, 6) + 'DIR=/data/adb/legion-r35-read\n' + s(10, 17)
    guards = s(28, 42) + s(49, 66) + GUARDS
    io = common + guards + s(68, 86) + IO  # tx_ok, select_page, read_reg only

    # R34's private mount/25 s DSI child; ESD restoration and unmount are
    # outside the timeout. Keep the supervisor silent and propagate cleanup rc.
    supervisor = (common + s(106, 116) + 'transaction() {\n' + s(124, 133)
                  + r(128, 128).replace('R34_IO', 'R35_IO') + io
                  + 'R35_IO\n}\ntransaction "$@"\n')
    entry = '#!/system/bin/sh\n' + common + s(20, 26) + guards + r(136, 139)
    entry += '\nsupervise() {\n    unshare -m /system/bin/sh -s -- "$1" "$2" <<\'R35_SUPERVISOR\'\n'
    entry += supervisor + 'R35_SUPERVISOR\n}\n\n' + r(141, 146)
    entry += '''    qualified "$1" "$epoch" || fail 'panel/stock/brightness mismatch'\n'''
    entry += r(155, 156) + r'''    fields=$(supervise "$1" "$epoch") || return "$?"
    [ -n "$fields" ] && qualified "$1" "$epoch" || fail 'snapshot incomplete or panel changed'
    printf 'R35_OK bl=%s epoch=%s %s page=0 esd=reg_read\n' "$1" "$epoch" "$fields"
}

[ "$#" -eq 1 ] && dbv_hex "$1" >/dev/null || fail 'usage: probe.sh {1024|3600|3601|4096}'
'''
    entry += r(178, 187).replace('@SESSION_SHA@', SESSION_SHA)

    for stage in (io, supervisor, entry):
        subprocess.run(['sh', '-n'], input=stage, text=True, check=True)

    # Audit the emitted script, not just a list used to generate it. All DSI
    # endpoint access, including recovery, must come from the pinned sources.
    dsi_lines = lambda text: [line for line in text.splitlines() if '$DSI/' in line]
    if dsi_lines(entry) != dsi_lines(s(124, 129) + s(68, 86)):
        raise ValueError('unexpected DSI endpoint access')
    expected_reads = {(0x23, addr, 1) for addr in (0xFE, 0x80, 0x82, 0xBA, 0xA9, 0xA4, 0xAD, 0xB4)}
    expected_reads.update(((0x23, 0xC1, 3), (0x23, 0xC2, 3), (0, 0x52, 2)))
    calls = re.findall(r'\$\(read_reg (0x\w+) ([123]) (0x\w+) \| octets \2\)', entry)
    if (len(calls) != len(expected_reads) or
            {(int(p, 16), int(a, 16), int(n)) for p, n, a in calls} != expected_reads or
            re.sub(r'(?m)^\s*#.*$', '', entry).count('read_reg') != len(calls) + 1 or
            entry.count('select_page') != s(68, 86).count('select_page')):
        raise ValueError('unexpected register/selector call or response length')
    return entry


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    script = build()
    if args.check:
        print('OK: pinned guards, 3 shell stages, 11 fixed reads, native selectors only')
    elif args.output:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
