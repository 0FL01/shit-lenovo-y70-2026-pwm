#!/usr/bin/env python3
"""Build the R37 native-stock reader offline: stdout, --check, or -o NEW_FILE.

Target: /data/adb/legion-r37-read/probe.sh {512|2048|3601} {0|1}
The arguments are expectations. The reader never changes brightness or DC.
The bounded R35 supervisor isolates ESD only during the six reads and verifies
reg_read on exit. The individual register reads are not one atomic transfer.
"""

import argparse
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys


R35 = Path(__file__).resolve().parents[1] / 'direct_camera_r35_20261120/build_reader.py'
R35_SHA = '753daaa899b558711fd65a42a9d2b9c77d2037c3bebc130e9cd613168c3e4779'

GUARDS = r'''
valid_args() {
    [ "$#" = 2 ] || return 1
    case "$1" in 512|2048|3601) ;; *) return 1 ;; esac
    case "$2" in 0|1) ;; *) return 1 ;; esac
}
qualified() {
    ready "$3" && [ "$(cat "$BL/brightness")" = "$1" ] &&
        [ "$(cat "$DRM/panelDC")" = "$2" ] &&
        provider=$(timeout 3 content call --uri content://com.motorola.android.providers.settings/global \
            --method GET_global --arg display_dc_mode_enabled) &&
        [ "$provider" = "Result: Bundle[{value=$2}]" ]
}
'''

FIELDS = r'''
{
bl=$1 dc=$2 epoch=$3
valid_args "$bl" "$dc" && qualified "$bl" "$dc" "$epoch" || exit 2
a9=$(read_reg 0x23 1 0xA9 | octets 1) &&
d9=$(read_reg 0x24 1 0x9D | octets 1) &&
r80=$(read_reg 0x23 1 0x80 | octets 1) &&
f81=$(read_reg 0x4F 1 0x81 | octets 1) &&
c1=$(read_reg 0x23 3 0xC1 | octets 3) &&
dbv=$(read_reg 0x00 2 0x52 | octets 2) || fail 'stock register read failed'
case "$dc/$a9/$d9/$r80" in
    0/0e/0e/50|1/8e/8e/90) ;; *) fail 'stock DC core mismatch' ;;
esac
[ "$dbv" = "$(printf '%04x' "$bl")" ] || fail 'panel DBV mismatch'
qualified "$bl" "$dc" "$epoch" || exit 2
printf 'A9=%s D9=%s R80=%s F81=%s C1=%s DBV=%s\n' "$a9" "$d9" "$r80" "$f81" "$c1" "$dbv"
} </dev/null
'''


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f'unexpected R35 shape: {old!r}')
    return text.replace(old, new)


def build():
    raw = R35.read_bytes()
    if sha256(raw).hexdigest() != R35_SHA:
        raise ValueError('review R35 builder after source drift')
    sys.path.insert(0,str(R35.parent));import build_reader as base
    script = base.build()  # includes R35's source pins, endpoint audit and parse checks
    s = base.pinned('06-tools/recipe_session.sh', base.SESSION_SHA)
    script = replace(script, 'legion-r35-read', 'legion-r37-read', 3)
    script = replace(script, s(62, 66) + base.GUARDS, GUARDS, 2)
    octets = base.IO.split('fingerprint() {', 1)[0]
    script = replace(script, base.IO, octets + FIELDS)
    script = replace(script, '''-- "$1" "$2" <<'R35_''', '''-- "$1" "$2" "$3" <<'R35_''', 2)
    script = replace(script, 'qualified "$1" "$epoch"', 'qualified "$1" "$2" "$epoch"', 2)
    script = replace(script, 'fields=$(supervise "$1" "$epoch")', 'fields=$(supervise "$1" "$2" "$epoch")')
    script = replace(script, "R35_OK bl=%s epoch=%s", "R37_OK bl=%s dc=%s epoch=%s")
    script = replace(script, '"$1" "$epoch" "$fields"', '"$1" "$2" "$epoch" "$fields"')
    script = replace(script, '[ "$#" -eq 1 ] && dbv_hex "$1" >/dev/null || fail \'usage: probe.sh {1024|3600|3601|4096}\'',
                     'valid_args "$@" || fail \'usage: probe.sh {512|2048|3601} {0|1}\'')

    # Audit the generated shell independently of the read/validation template.
    code = re.sub(r'(?m)^\s*#.*$', '', script)
    calls = re.findall(r'\$\(read_reg (0x\w+) (\d+) (0x\w+) \| octets \2\)', code)
    if calls != [('0x23', '1', '0xA9'), ('0x24', '1', '0x9D'), ('0x23', '1', '0x80'),
                 ('0x4F', '1', '0x81'), ('0x23', '3', '0xC1'), ('0x00', '2', '0x52')] or code.count('read_reg') != 7:
        raise ValueError('unexpected register operation')
    dsi = lambda text: [line for line in text.splitlines() if '$DSI/' in line]
    if (dsi(script) != dsi(s(124, 129) + s(68, 86)) or code.count('select_page') != 4
            or re.findall(r'(?<![<>])>(?![>&])\s*"([^"\n]+)"', code) != ['$ESD', '$ESD', '$DSI/tx_cmd', '$DSI/rx_cmd']
            or 'PUT_global' in code or s(106,116) not in script or s(130,133) not in script):
        raise ValueError('unexpected selector, setter or endpoint write')
    for stage in (script, heredoc(script, 'R35_SUPERVISOR'), heredoc(script, 'R35_IO')):
        subprocess.run(['sh', '-n'], input=stage, text=True, check=True)
    return script


def heredoc(script, name):
    return script.split(f"<<'{name}'\n", 1)[1].split(f'\n{name}\n', 1)[0] + '\n'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    script = build()
    if args.check:
        print('OK: 3 stages, 6 fixed reads, selector-only TX, GET-only provider, bounded R35 ESD restore')
    elif args.output:
        import os
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700), 'w') as out:
            out.write(script)
    else:
        sys.stdout.write(script)


if __name__ == '__main__':
    main()
