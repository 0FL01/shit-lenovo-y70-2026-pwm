#!/usr/bin/env python3
"""Build the temporary R34/DBV512 one-shot, entirely offline.

Default: shell to stdout; --check: validate only; -o FILE: create a new file.
Target entry: /data/adb/legion-r34-probe/probe.sh stock-check; then use
apply{92,9e,a9}, check{92,9e,a9} or restore{92,9e,a9} in that wake epoch.
The directory and script must already be root:0700. No installation or watcher.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SESSION_SHA = '156868ca536a1a8ccf95183cc3dbc46fbfc112ed12df70cc39c958ce89cb9bd9'
# Private R22 transcripts r22_r26_9d92_apply.txt, r22_r24_9d9e_apply.txt and
# their *_ret.txt: 512 / C1=00 00 10 (stock 00 02 be). R5 also exercised A9
# alone at 512, C1=00 00 10. Verify the matching transmitted A9 table below.
PROFILES = {
    'stock': (0x0e, 0x0e, 0x50), '92': (0x8e, 0x92, 0x90),
    '9e': (0x8e, 0x9e, 0x90), 'a9': (0x8e, 0x0e, 0x50),
}
KEYS = ((0x23, 0xa9), (0x24, 0x9d), (0x23, 0x80))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def packets(raw):
    while raw:
        length = int.from_bytes(raw[5:7], 'big')
        require(0 < length <= len(raw) - 7, 'truncated DSI descriptor')
        yield raw[:7], raw[7:7 + length]
        raw = raw[7 + length:]


def verify_a9_history():
    artifacts = ROOT / 'artifacts'
    raw = (artifacts / 'dsi_selector_split_20261107/a9_only.bin').read_bytes()
    run = json.loads((artifacts / 'a9_a001_20261108_01/run.json').read_bytes())
    require(hashlib.sha256(raw).hexdigest() == run['authorization']['program_sha256']['a9_only'],
            'A9 archive program does not match run')
    stages = run['stages']
    require([s['label'] for s in stages] == ['baseline', 'a9_only', 'return_a9_only']
            and run['stock_return_verified'] is True and run['series_complete'] is True,
            'A9 archive lacks stock -> A9 -> stock')
    page, core = None, []
    program = list(packets(raw))
    for _, data in program:
        if len(data) == 4 and data[:3] == bytes.fromhex('ff 5a a5'):
            page = data[3]
        elif (page, data[0]) in KEYS:
            core.append(((page, data[0]), data[1:]))
    require(core == list(zip(KEYS, (bytes([v]) for v in PROFILES['a9'])))
            and all(s['native_packets_matched'] == len(program) == 75 for s in stages),
            'A9 core not verified in archived native transmission')
    for s, profile in zip(stages, ('stock', 'a9', 'stock')):
        rx = s['readback']['values']
        require((rx['23:A9'], rx['24:9D']) == tuple([v] for v in PROFILES[profile][:2]),
                'A9 archive readback mismatch')


# R5 A9-only apply/return: exactly the FIRST selector/write/page-zero triplet
# of core_packets. The other two core registers are read for evidence only.
A9_PACKETS = r'''
a9_packets() { printf '%s' "$PAGE 0x23 0x39 0 0 0 0 0 2 0xA9 $1 $PAGE 0x00"; }
'''

IO = r'''
a9_only() {
    a9_packets "$1" > "$DIR/core.tx" && panel_on || return 1
@DD@
}

receipt() {
    a9=$(read_reg 0x23 1 0xA9) && d9=$(read_reg 0x24 1 0x9D) &&
        r80=$(read_reg 0x23 1 0x80) && c1=$(read_reg 0x23 3 0xC1) &&
        dbv=$(read_reg 0x00 2 0x52) || return 1
    printf 'receipt=%s profile=%s epoch=%s A9=%s 9D=%s 80=%s C1="%s" 00:52="%s" page=0\n' \
        "$2" "$1" "$epoch" "$a9" "$d9" "$r80" "$c1" "$dbv" || return 1
    case "$1" in
@EXPECT@
        *) return 5 ;;
    esac
    [ "$a9/$d9/$r80/$c1/$dbv" = "$expected/0x02 0x00" ] || return 5
}

# The shell itself reads this stage from a heredoc; utilities get no script input.
{
action=$1 epoch=$2
case "$action" in
@ROUTES@
    *) exit 1 ;;
esac
ready "$epoch" || exit 2
stock_off || exit 4
receipt "$before" entry || exit "$?"
if [ -n "$after" ]; then
    ready "$epoch" || exit 2
    stock_off || exit 4
    case "$action" in
@WRITES@
        *) exit 1 ;;
    esac || exit "$?"
    receipt "$after" result || exit "$?"
fi
ready "$epoch" || exit 2
stock_off || exit 4
} </dev/null
'''


SUPERVISOR = r'''
# In unshare -m. Only this supervisor changes ESD. Its timeout covers the DSI
# child, never cleanup. No blind page/DSI operation on a timeout or TX error.
transaction() {
@MOUNT@
    trap 'rc=$?; if cleanup; then printf "ESD_RESTORED reg_read io_rc=%s\n" "$rc"; else rc=7; fi; exit "$rc"' EXIT
@ENABLE_ESD@
    timeout -k 3 25 /system/bin/sh -s -- "$1" "$2" <<'R34_IO'
@IO@R34_IO
}
transaction "$@"
'''


ENTRY = r'''
SELF=$DIR/probe.sh
SESSION=/data/adb/legion-dc-session
private_dir() { [ -d "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%a' "$1")" = 0:700 ]; }
private_script() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%a:%h' "$1")" = 0:700:1 ]; }

run_locked() {
    # Same inode and lock order as start_session; mksh inherits function FDs.
    flock -n 8 || fail 'session control busy'
    flock -n 9 || fail 'session worker busy; stop it first'
    identify && [ "$(getprop ro.boot.hardware.revision)" = pvt ] || fail 'target/build/module/panel mismatch'
    epoch=$(awake_epoch) || fail 'no stable awake epoch'
    [ "$#" -eq 1 ] || [ "$2" = "$epoch" ] || fail 'wake epoch mismatch'
    boot=$(cat /proc/sys/kernel/random/boot_id) && [ "${#boot}" = 36 ] || fail 'missing boot ID'
    if [ "$1" != stock-check ]; then
        [ -f "$DIR/stock.epoch" ] && [ ! -L "$DIR/stock.epoch" ] &&
            [ "$(stat -c '%u:%a:%h' "$DIR/stock.epoch")" = 0:600:1 ] &&
            [ "$(cat "$DIR/stock.epoch")" = "$boot:$epoch" ] || fail 'need stock-check in this wake'
    fi
    ready "$epoch" && stock_off || fail 'panel not ready or stock toggle not OFF'
    [ -d "$DBG" ] || mkdir -m 700 "$DBG" || exit 1
    private_dir "$DBG" || fail 'unexpected debugfs mountpoint'
    if [ -e "$DIR/core.tx" ] || [ -L "$DIR/core.tx" ]; then
        [ ! -L "$DIR/core.tx" ] && [ -f "$DIR/core.tx" ] &&
            [ "$(stat -c '%u:%a:%h' "$DIR/core.tx")" = 0:600:1 ] || fail 'unexpected core.tx'
    fi
    unshare -m /system/bin/sh -s -- "$1" "$epoch" <<'R34_SUPERVISOR'
@SUPERVISOR@R34_SUPERVISOR
    rc=$?
    [ "$rc" = 0 ] || return "$rc"
    ready "$epoch" && stock_off || fail 'panel changed before completion'
    if [ "$1" = stock-check ]; then
        token=$(mktemp "$DIR/stock.XXXXXX") && printf '%s:%s\n' "$boot" "$epoch" > "$token" &&
            mv -f "$token" "$DIR/stock.epoch" || fail 'could not record verified stock epoch'
    fi
    printf 'R34_OK action=%s epoch=%s\n' "$1" "$epoch"
}

case "${1:-}" in
    stock-check) [ "$#" -eq 1 ] || [ "$#" -eq 2 ] || fail 'stock-check [EPOCH]' ;;
    @ACTIONS@) [ "$#" -eq 1 ] || [ "$#" -eq 2 ] || fail 'expected action [EPOCH]' ;;
    *) fail 'unknown R34 action' ;;
esac
[ "$(id -u)" = 0 ] && [ "$0" = "$SELF" ] && private_dir "$DIR" && private_script "$SELF" ||
    fail 'expected absolute probe path and root:0700 staging'
private_dir "$SESSION" && private_script "$SESSION/recipe_session.sh" &&
    printf '%s  %s\n' '@SESSION_SHA@' "$SESSION/recipe_session.sh" | sha256sum -c -s ||
    fail 'installed session applier mismatch'
for lock in "$SESSION/control.lock" "$SESSION/worker.lock"; do
    [ -f "$lock" ] && [ ! -L "$lock" ] || fail 'expected installed session lock inodes'
done
# Read-only opens: flock(2) on these local inodes does not require truncation.
run_locked "$@" 8< "$SESSION/control.lock" 9< "$SESSION/worker.lock"
'''


def build():
    raw = (ROOT / '06-tools/recipe_session.sh').read_bytes()
    # This digest checks *all* slices below (including their offsets and EOLs)
    # and the control/worker protocol of the installed cooperating executable.
    require(hashlib.sha256(raw).hexdigest() == SESSION_SHA, 'recipe_session.sh drift')
    lines = raw.decode('ascii').splitlines(keepends=True)

    def src(first, last):
        return ''.join(lines[first - 1:last])

    def fill(template, **fields):
        return re.sub(r'@([A-Z_]+)@', lambda m: fields[m[1]], template)

    verify_a9_history()
    common = src(3, 6) + '\nDIR=/data/adb/legion-r34-probe\n' + src(10, 17)
    guards = src(28, 42) + src(49, 66)
    routes = {'stock-check': ('stock', '')}
    expected, writes = [], []
    for name, values in PROFILES.items():
        c1 = '0x00 0x02 0xbe' if name == 'stock' else '0x00 0x00 0x10'
        words = [f'0x{v:02x}' for v in values]
        expected.append(f"        {name}) expected='{'/'.join(words)}/{c1}' ;;")
        if name != 'stock':
            routes.update({f'apply{name}': ('stock', name), f'check{name}': (name, ''),
                           f'restore{name}': (name, 'stock')})
    for action, (_, after) in routes.items():
        if after:
            words = [f'0x{v:02x}' for v in PROFILES[after]]
            call = f'a9_only {words[0]}' if action.endswith('a9') else f"apply_core {' '.join(words)}"
            writes.append(f'        {action}) {call} ;;')
    route_cases = [f"    {action}) before={before}; after='{after}' ;;"
                   for action, (before, after) in routes.items()]
    io = common + guards + src(68, 104) + A9_PACKETS + fill(
        IO, DD=src(98, 101).rstrip(), EXPECT='\n'.join(expected),
        WRITES='\n'.join(writes), ROUTES='\n'.join(route_cases))
    supervisor = common + src(106, 116) + fill(
        SUPERVISOR, MOUNT=src(124, 129).rstrip(), ENABLE_ESD=src(131, 133).rstrip(), IO=io)
    entry = '#!/system/bin/sh\n# Generated temporary R34 one-shot; DBV 512 only.\n'
    entry += common + src(20, 26) + guards + fill(
        ENTRY, SUPERVISOR=supervisor, SESSION_SHA=SESSION_SHA,
        ACTIONS='|'.join(a for a in routes if a != 'stock-check'))

    # Heredocs are data to the outer parser: syntax-check all three shells.
    for script in (entry, supervisor, io):
        subprocess.run(['sh', '-n'], input=script, text=True, check=True)
    # Exercise only the pure serializer on the host, then independently decode
    # all headers, opcodes, page returns and data bytes for each allowed target.
    for profile, only_a9 in [('stock', False), ('92', False), ('9e', False), ('a9', True), ('stock', True)]:
        values = PROFILES[profile][:1 if only_a9 else 3]
        func = 'a9_packets' if only_a9 else 'core_packets'
        text = subprocess.check_output(['sh', '-c', src(15, 15) + src(88, 91) + A9_PACKETS + func + ' "$@"',
                                        'r34-validate', *(f'0x{v:02x}' for v in values)], text=True)
        raw = bytes(int(word, 0) for word in text.split())
        selector = bytes.fromhex('ff 5a a5')
        payloads = [data for (page, reg), v in zip(KEYS, values)
                    for data in (selector + bytes([page]), bytes([reg, v]), selector + b'\0')]
        require(len(raw) == (31 if only_a9 else 93) and list(packets(raw)) == [
            (bytes([0x39, 0, 0, 0, 0, 0, len(data)]), data) for data in payloads],
            'grouped native payload mismatch')
    return entry


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    script = build()
    if args.check:
        print('OK: session source, A9 archive, 3 shell stages, 3 core (93 B) and 2 A9-only (31 B) payloads')
    elif args.output:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
