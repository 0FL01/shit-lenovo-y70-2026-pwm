#!/usr/bin/env python3
"""Build the offline R49 one-shot (stdout, --check, or -o NEW_FILE).

Stage root:0700 at /data/adb/legion-r49-probe/probe.sh in a fresh root:0700
directory. Actions take an optional expected wake epoch; recover-stock requires
it and only verifies stock in a different wake of the same boot. Keep the
original epoch seal and journals for the whole experiment. This script does not
change brightness, mode or session policy; the caller owns the independent
deadline and panel recovery on uncertainty.
"""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SESSION_SHA = '156868ca536a1a8ccf95183cc3dbc46fbfc112ed12df70cc39c958ce89cb9bd9'
R34_SHA = 'd0e6b490195faf2f3e9e20c8ad35579a19959b386567e8770fe50e709235b2b2'
R35_SHA = '753daaa899b558711fd65a42a9d2b9c77d2037c3bebc130e9cd613168c3e4779'
DIR = '/data/adb/legion-r49-probe'
ACTIONS = 'stock-check|enter|checkA|checkB|candidate|revert|stock|dry-revert|recover-stock'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pinned(path, digest):
    raw = (ROOT / path).read_bytes()
    require(sha256(raw).hexdigest() == digest, f'review pinned source drift: {path}')
    lines = raw.decode('ascii').splitlines(keepends=True)
    return lambda first, last: ''.join(lines[first - 1:last])


GUARDS = r'''
hwc_120() {
    # Require a parsed activeMode, and reject any conflicting or malformed one.
    timeout 3 dumpsys SurfaceFlinger | awk '
        { line=$0
          while (match(line, /activeMode=\{[^}]*\}/)) {
            mode=substr(line,RSTART,RLENGTH)
            line=substr(line,RSTART+RLENGTH)
            if (mode !~ /^activeMode=\{id=[0-9]+, hwcId=0, [^}]*vsyncRate=120\.00 Hz([,}]| )/) bad=1
            seen++
          }
          if (line ~ /activeMode=\{/) bad=1
        }
        END { exit (!seen || bad) }'
}
qualified() {
    ready "$1" && stock_off && [ "$(cat "$BL/brightness")" = 512 ] && hwc_120
}
'''

PACKETS = r'''
param_packets() { printf '%s' "$PAGE 0x24 0x39 0 0 0 0 0 2 0x9E $1 $PAGE 0x00"; }
'''

RECEIPT = r'''
receipt() {
    # A fresh read_reg transaction for each field, including independent DBV
    # on page 0. No qualified 00:FE short read exists in R35/R39.
    low=$(read_reg 0x24 1 0x9E | octets 1) &&
        a9=$(read_reg 0x23 1 0xA9 | octets 1) &&
        d9=$(read_reg 0x24 1 0x9D | octets 1) &&
        r80=$(read_reg 0x23 1 0x80 | octets 1) &&
        c1=$(read_reg 0x23 3 0xC1 | octets 3) &&
        dbv=$(read_reg 0x00 2 0x52 | octets 2) || return 1
    printf 'receipt=%s profile=%s epoch=%s 9E=%s A9=%s 9D=%s 80=%s C1=%s 00:52=%s page=0\n' \
        "$2" "$1" "$epoch" "$low" "$a9" "$d9" "$r80" "$c1" "$dbv" || return 1
    [ "$dbv" = 0200 ] || return 5
    case "$1/$low/$a9/$d9/$r80/$c1" in
        stock/11/0e/0e/50/0002be|A/11/8e/8e/90/000010|B/91/8e/8e/90/??????) return 0 ;;
        *) return 5 ;;
    esac
}
'''

IO = r'''
{
action=$1 epoch=$2
case "$action" in
    stock-check|recover-stock) before=stock; after= ;;
    enter)       before=stock; after=A ;;
    checkA|dry-revert) before=A; after= ;;
    checkB)      before=B; after= ;;
    candidate)   before=A; after=B ;;
    revert)      before=B; after=A ;;
    stock)       before=A; after=stock ;;
    *) exit 1 ;;
esac
qualified "$epoch" || exit 2
receipt "$before" entry || exit "$?"
if [ -n "$after" ]; then
    qualified "$epoch" || exit 2
    case "$action" in
        enter)     apply_core 0x8e 0x8e 0x90 ;;
        candidate) write_9e 0x91 ;;
        revert)    write_9e 0x11 ;;
        stock)     apply_core 0x0e 0x0e 0x50 ;;
        *) exit 1 ;;
    esac || exit "$?"
    receipt "$after" result || exit "$?"
fi
qualified "$epoch" || exit 2
} </dev/null
'''

SUPERVISOR = r'''
# Adapt R34: only the DSI child is timed; its journalled stdout goes to a
# local file so losing the host pipe cannot interrupt qualification of B.
finish() {
    rc=$1
    cleanup || exit 7
    if [ -n "$journal" ]; then
        if [ "$rc" = 0 ]; then
            # A successful child implies native TX and exact post-readback;
            # publish proof only AFTER the supervisor verifies ESD restoration.
            printf '%s\n' "$token" > "$journal/observed.tmp" &&
                mv "$journal/observed.tmp" "$journal/observed" || rc=8
        fi
        [ ! -f "$journal/io.log" ] || cat "$journal/io.log"
    fi
    printf 'ESD_RESTORED reg_read io_rc=%s\n' "$rc"
    exit "$rc"
}
transaction() {
    action=$1 epoch=$2 token=$3 journal=
    case "$action" in candidate|revert) journal=$DIR/$action.once ;; esac
@MOUNT@
    trap 'finish "$?"' EXIT
    trap 'exit 30' HUP INT TERM
@ENABLE_ESD@
    (
        if [ -n "$journal" ]; then exec > "$journal/io.log" || exit 8; fi
        timeout -k 3 25 /system/bin/sh -s -- "$action" "$epoch" <<'R49_IO'
@IO@R49_IO
    )
}
transaction "$@"
'''

JOURNAL = r'''
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
private_record() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%a:%h' "$1")" = 0:600:1 ];
}
wake_gate() {
    stamp=$DIR/stock.epoch
    if absent "$stamp"; then
        [ "$1" = stock-check ]
        return
    fi
    private_record "$stamp" && prior=$(cat "$stamp") || return 1
    if [ "$1" != recover-stock ]; then
        # Once sealed, even stock-check cannot reopen the staging directory.
        [ "$prior" = "$token" ]
        return
    fi
    [ "$#" -eq 2 ] && [ "$2" = "$epoch" ] || return 1
    case "$prior" in "$boot":*) prior_wake=${prior#*:} ;; *) return 1 ;; esac
    case "$prior_wake" in ''|*[!0-9]*) return 1 ;; esac
    [ "$prior_wake" != "$epoch" ]
}
proved() {
    private_dir "$DIR/$1.once" && private_record "$DIR/$1.once/observed" &&
        [ "$(cat "$DIR/$1.once/observed")" = "$token" ];
}
journal_gate() {
    if absent "$DIR/candidate.once"; then
        absent "$DIR/revert.once" && [ "$1" != checkB ] && [ "$1" != revert ]
    elif ! proved candidate; then
        return 1 # Candidate claim consumed: recovery outside this executor.
    elif absent "$DIR/revert.once"; then
        case "$1" in checkB|revert) return 0 ;; *) return 1 ;; esac
    elif ! proved revert; then
        return 1 # Revert claim consumed: recovery outside this executor.
    else
        case "$1" in checkA|dry-revert|stock|stock-check) return 0 ;; *) return 1 ;; esac
    fi
}
'''

ENTRY = r'''
    action=$1
    [ "$#" -eq 1 ] || [ "$2" = "$epoch" ] || fail 'wake epoch mismatch'
    boot=$(cat /proc/sys/kernel/random/boot_id) && [ "${#boot}" = 36 ] || fail 'missing boot ID'
    token=$boot:$epoch
    wake_gate "$@" || fail 'stock epoch seal does not admit action; recover-stock requires explicit new wake in same boot'
    qualified "$epoch" || fail 'panel, stock toggle, BL 512 or HWC 0/120 mismatch'
    # A new wake admits only read-only recovery; leave an uncertain journal intact.
    [ "$action" = recover-stock ] || journal_gate "$action" || fail 'journal does not admit action; no DSI or retry'
@STAGING@
    # Reserve before any panel I/O (even the entry readback). Never remove or
    # overwrite these directories, including when the attempt fails or times out.
    case "$action" in
        candidate|revert) mkdir -m 700 "$DIR/$action.once" || fail 'action already claimed' ;;
    esac
    unshare -m /system/bin/sh -s -- "$action" "$epoch" "$token" <<'R49_SUPERVISOR'
@SUPERVISOR@R49_SUPERVISOR
    rc=$?
    [ "$rc" = 0 ] || return "$rc"
    qualified "$epoch" || fail 'panel changed before completion'
    if [ "$action" = stock-check ] && absent "$DIR/stock.epoch"; then
        record=$(mktemp "$DIR/stock.XXXXXX") && printf '%s\n' "$token" > "$record" &&
            mv "$record" "$DIR/stock.epoch" || fail 'could not seal verified stock epoch'
    fi
    printf 'R49_OK action=%s epoch=%s page=0 esd=reg_read\n' "$action" "$epoch"
}

[ "$#" -eq 1 ] || [ "$#" -eq 2 ] || fail 'usage: probe.sh ACTION [EPOCH]; recover-stock EPOCH requires EPOCH'
case "$1" in @ACTIONS@) ;; *) fail 'unknown R49 action' ;; esac
'''


def shell(text, *args, check=True):
    return subprocess.run(['sh', '-s', '--', *args], input=text, text=True,
                          capture_output=True, check=check)


def verify(s, octets):
    for value in ('91', '11'):
        data = shell(s(15, 15) + PACKETS + f'param_packets 0x{value}\n').stdout
        raw = bytes(int(word, 0) for word in data.split())
        require(len(raw) == 31 and raw == bytes.fromhex(
            f'39000000000004ff5aa524 390000000000029e{value} 39000000000004ff5aa500'),
            'wrong 9E wire list')
    for profile, values in (('A', '0x8e 0x8e 0x90'), ('stock', '0x0e 0x0e 0x50')):
        data = shell(s(15, 15) + s(88, 91) + f'core_packets {values}\n').stdout
        raw = bytes(int(word, 0) for word in data.split())
        expected = {'A': '8e 8e 90', 'stock': '0e 0e 50'}[profile].split()
        require(len(raw) == 93 and all(
            raw[i * 31:(i + 1) * 31] == bytes.fromhex(
                f'39000000000004ff5aa5{page} 39000000000002{reg}{v} 39000000000004ff5aa500')
            for i, ((page, reg), v) in enumerate(zip((('23', 'a9'), ('24', '9d'), ('23', '80')), expected))),
            'wrong core wire list')

    # Replay the emitted I/O routing and actual receipt parser; no device I/O.
    mocks = r'''
qualified() { [ "$1" = 123 ]; }
read_reg() {
    case "$1/$2/$3" in
        0x24/1/0x9E) [ "$state" != B ] && echo 0x11 || echo 0x91 ;;
        0x23/1/0xA9|0x24/1/0x9D) [ "$state" = stock ] && echo 0x0e || echo 0x8e ;;
        0x23/1/0x80) [ "$state" = stock ] && echo 0x50 || echo 0x90 ;;
        0x23/3/0xC1) case "$state" in stock) echo 0x00 0x02 0xbe ;; A) echo 0x00 0x00 0x10 ;; B) echo 0xaa 0xbb 0xcc ;; esac ;;
        0x00/2/0x52) printf '%s\n' "$mock_dbv" ;;
        *) return 1 ;;
    esac
}
apply_core() {
    printf 'WRITE core %s\n' "$*"
    case "$*" in '0x8e 0x8e 0x90') state=A ;; '0x0e 0x0e 0x50') state=stock ;; *) return 6 ;; esac
}
write_9e() {
    printf 'WRITE 9E %s\n' "$1"
    [ "$write_rc" = 0 ] || return "$write_rc"
    case "$1" in 0x91) state=B ;; 0x11) state=A ;; *) return 6 ;; esac
}
'''
    cases = {
        'stock-check': ('stock', '', ''), 'recover-stock': ('stock', '', ''),
        'enter': ('stock', 'core 0x8e 0x8e 0x90', 'A'),
        'checkA': ('A', '', ''), 'checkB': ('B', '', ''), 'dry-revert': ('A', '', ''),
        'candidate': ('A', '9E 0x91', 'B'), 'revert': ('B', '9E 0x11', 'A'),
        'stock': ('A', 'core 0x0e 0x0e 0x50', 'stock'),
    }
    for action, (state, write, after) in cases.items():
        fixture = mocks + f"state={state}; mock_dbv='0x02 0x00'; write_rc=0\n"
        out = shell(fixture + octets + RECEIPT + IO, action, '123').stdout
        writes = [line for line in out.splitlines() if line.startswith('WRITE ')]
        require(writes == (['WRITE ' + write] if write else []) and
                f'receipt=entry profile={state} ' in out and
                (f'receipt=result profile={after} ' in out if after else 'receipt=result' not in out) and
                ('C1=aabbcc' in out if 'B' in (state, after) else True), f'bad replay: {action}')
    for action, fixture, rc, writes in (
            ('candidate', "state=A; mock_dbv='0x02 0x01'; write_rc=0", 5, 0),
            ('candidate', "state=A; mock_dbv='0x02 0x00 0x00'; write_rc=0", 1, 0),
            ('candidate', "state=B; mock_dbv='0x02 0x00'; write_rc=0", 5, 0),
            ('candidate', "state=A; mock_dbv='0x02 0x00'; write_rc=6", 6, 1),
            ('revert', "state=A; mock_dbv='0x02 0x00'; write_rc=0", 5, 0),
            ('recover-stock', "state=B; mock_dbv='0x02 0x00'; write_rc=0", 5, 0),
            ('invalid', "state=A; mock_dbv='0x02 0x00'; write_rc=0", 1, 0)):
        out = shell(mocks + fixture + '\n' + octets + RECEIPT + IO, action, '123', check=False)
        require(out.returncode == rc and out.stdout.count('WRITE ') == writes and
                'receipt=result' not in out.stdout, f'bad refusal: {action} {fixture}')

    journal_actions = set(cases) - {'recover-stock'}
    for candidate, revert, admitted in (
            ('absent', 'absent', journal_actions - {'checkB', 'revert'}),
            ('claimed', 'absent', set()), ('proved', 'absent', {'checkB', 'revert'}),
            ('proved', 'claimed', set()), ('proved', 'proved', {'checkA', 'dry-revert', 'stock', 'stock-check'}),
            ('absent', 'claimed', set())):
        fixture = JOURNAL + f'\nDIR={DIR}; c={candidate}; r={revert}\n' + r'''
absent() { case "$1" in */candidate.once) [ "$c" = absent ] ;; */revert.once) [ "$r" = absent ] ;; esac; }
proved() { case "$1" in candidate) [ "$c" = proved ] ;; revert) [ "$r" = proved ] ;; esac; }
for action; do if journal_gate "$action"; then printf '%s\n' "$action"; fi; done
'''
        require(set(shell(fixture, *sorted(journal_actions)).stdout.splitlines()) == admitted, 'bad journal replay')

    # Exercise the original epoch seal with an absent, untrusted, current,
    # old or foreign-boot record. Recovery must never reopen the writer routes.
    for stamp_state, saved, admitted in (
            ('absent', '', {'stock-check'}),
            ('untrusted', 'boot:122', set()),
            ('sealed', 'boot:123', journal_actions),
            ('sealed', 'boot:122', {'recover-stock'}),
            ('sealed', 'other:122', set()),
            ('sealed', 'boot:', set()),
            ('sealed', 'boot:122:123', set())):
        fixture = JOURNAL + f"\nDIR={DIR}; boot=boot; epoch=123; token=boot:123; kind={stamp_state}; saved='{saved}'\n" + r'''
absent() { [ "$kind" = absent ]; }
private_record() { [ "$kind" = sealed ]; }
cat() { printf '%s\n' "$saved"; }
for action; do if wake_gate "$action" 123; then printf '%s\n' "$action"; fi; done
if wake_gate recover-stock || wake_gate recover-stock 122; then exit 9; fi
'''
        require(set(shell(fixture, *cases).stdout.splitlines()) == admitted, 'bad wake seal replay')

    for modes, good in ((['0, 120.00'], True), (['0, 120.00'] * 2, True),
                        (['0, 120.00', '3, 144.00'], False), (['0, 60.00'], False), ([], False)):
        lines = [f'activeMode={{id=1, hwcId={mode.split(", ")[0]}, width=1440, vsyncRate={mode.split(", ")[1]} Hz}}' for mode in modes]
        fixture = "timeout() { printf '%s\\n' " + ' '.join(f"'{line}'" for line in lines) + '; }\n'
        require((shell(GUARDS + fixture + 'hwc_120\n', check=False).returncode == 0) == good,
                'wrong active mode qualification')


def build():
    s = pinned('06-tools/recipe_session.sh', SESSION_SHA)
    r = pinned('artifacts/direct_camera_r34_20261120/build_probe.py', R34_SHA)
    reader = pinned('artifacts/direct_camera_r35_20261120/build_reader.py', R35_SHA)
    common = s(3, 6) + f'DIR={DIR}\n' + s(10, 17)
    guards = s(28, 42) + s(49, 66) + GUARDS
    octets = reader(41, 49)
    write_9e = ('\nwrite_9e() {\n'
                '    param_packets "$1" > "$DIR/core.tx" && panel_on || return 1\n'
                + s(98, 101) + '    printf \'TX_OK 24:9E=%s page=0\\n\' "$1"\n}\n')
    io = common + guards + s(68, 104) + PACKETS + write_9e + octets + RECEIPT + IO
    supervisor = (common + s(106, 116) + SUPERVISOR.replace('@MOUNT@', s(124, 129).rstrip())
                  .replace('@ENABLE_ESD@', s(132, 133).rstrip()).replace('@IO@', io))
    entry = ('#!/system/bin/sh\n# Generated R49 one-shot; DBV 512 and HWC 0/120 only.\n'
             + common + s(20, 26) + guards + r(136, 139) + JOURNAL + r(141, 146)
             + ENTRY.replace('@STAGING@', r(155, 160).rstrip()).replace('@SUPERVISOR@', supervisor)
             .replace('@ACTIONS@', ACTIONS) + r(178, 187).replace('@SESSION_SHA@', SESSION_SHA))
    for stage in (io, supervisor, entry):
        subprocess.run(['sh', '-n'], input=stage, text=True, check=True)
    verify(s, octets)
    return entry


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    script = build()
    if args.check:
        print('OK: pinned scaffold, 3 shells, 31/93 B lists, route/readback/journal/wake seal/mode replay')
    elif args.output:
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
