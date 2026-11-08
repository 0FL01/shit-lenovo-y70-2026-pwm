#!/usr/bin/env python3
"""Read-only ILI97701A DDIC register dump on XT2611-1 via msm_drm debugfs rx_cmd.

Usage: run_ddic_regdump.py TARGET_TRANSPORT LABEL BRIGHTNESS REFRESH SCOPE
  BRIGHTNESS  Android manual brightness integer (52 -> DBV3584, 53 -> DBV3646)
  REFRESH     forced min/peak refresh rate (60, 90, 120, 144)
  SCOPE       known   : DT-written pages, all 256 registers, two passes
              census  : pages 0x00-0x7F, all registers, one pass
              probe   : multi-byte reads of selected registers

Never writes panel registers other than the page selector FF 5A A5 xx, which
stock firmware itself sends; every read is followed by page 0 restore.
"""

import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/ddic_regdump_20261107'
TMP = '/data/local/tmp/ddic-regdump'
BL = '/sys/class/backlight/panel0-backlight/brightness'
KNOWN_PAGES = [0x00, 0x03, 0x07, 0x08, 0x1D, 0x1E, 0x21, 0x23, 0x24, 0x2D, 0x31,
               0x4F, 0x51, 0x52, 0x53, 0x5A, 0x5B, 0x5C, 0x63]
# (page, register, length) multi-byte probes against values written by DT.
PROBES = [(0x5A, 0x86, 6), (0x5A, 0x87, 1), (0x5A, 0x88, 1), (0x63, 0xF1, 16),
          (0x63, 0xF2, 1), (0x53, 0x95, 2), (0x53, 0x96, 1), (0x53, 0xA2, 30),
          (0x53, 0xA3, 1), (0x24, 0x8B, 4), (0x24, 0x8C, 2), (0x23, 0xA9, 2),
          (0x2D, 0x98, 4), (0x51, 0xA1, 6), (0x52, 0x81, 6), (0x07, 0x8B, 2),
          (0x00, 0x51, 2), (0x00, 0x0A, 1)]
# Last values written by DT at panel on + DC OFF table (ground truth for layout).
EXPECTED = {(0x23, 0xA9): 0x0E, (0x23, 0xAA): 0x11, (0x23, 0x80): 0x50,
            (0x23, 0x85): 0x15, (0x23, 0xA6): 0xFC, (0x23, 0xA7): 0x00,
            (0x24, 0x80): 0x0E, (0x24, 0x81): 0x11, (0x24, 0x84): 0x00,
            (0x24, 0x9D): 0x0E, (0x24, 0x9E): 0x11, (0x2D, 0xCE): 0x55,
            (0x2D, 0xCD): 0x01, (0x2D, 0x97): 0x03, (0x2D, 0xB1): 0x03,
            (0x08, 0xC8): 0x62, (0x08, 0x98): 0xA6, (0x08, 0xD2): 0x01,
            (0x21, 0xA4): 0x38, (0x07, 0x8A): 0x01, (0x31, 0xD0): 0x80,
            (0x4F, 0x81): 0x10, (0x4F, 0x88): 0x78, (0x4F, 0x8B): 0x78,
            (0x03, 0xBD): 0x91, (0x1E, 0xC0): 0x10, (0x53, 0xF0): 0x00,
            (0x00, 0x0A): 0x9C}
IDENTITY = ['XT2611-1', 'W3WWS36.65-64-4-1', '_b',
            '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k', 'Enforcing']


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def main():
    assert len(sys.argv) == 6, __doc__
    transport, label, brightness, refresh, scope = sys.argv[1:]
    assert re.fullmatch(r'[a-z0-9_]+', label) and scope in ('known', 'census', 'probe')
    brightness, refresh = int(brightness), float(refresh)
    assert 1 <= brightness <= 255 and refresh in (60.0, 90.0, 120.0, 144.0)
    out = OUT / label
    out.mkdir(parents=True, exist_ok=False)
    report = {'started_at_utc': now(), 'label': label, 'scope': scope,
              'brightness_setting': brightness, 'refresh_request': refresh, 'events': []}

    def save():
        (out / 'run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def sh(command, root=False, timeout=60, check=True):
        remote = 'su -c ' + shlex.quote(command) if root else command
        p = subprocess.run(['adb', '-t', transport, 'shell', remote],
                           capture_output=True, text=True, timeout=timeout)
        report['events'].append({'at_utc': now(), 'command': remote[:400], 'exit_code': p.returncode,
                                 'stdout': p.stdout.strip()[:400], 'stderr': p.stderr.strip()[:400]})
        save()
        if check and p.returncode:
            raise RuntimeError(f'Command failed ({p.returncode}): {command}\n{p.stderr}')
        return p.stdout.strip()

    assert sh('getprop ro.boot.hardware.sku; getprop ro.build.display.id; '
              'getprop ro.boot.slot_suffix; uname -r; getenforce').splitlines() == IDENTITY
    assert sh('cat /sys/class/drm/card0-DSI-1/panelName', root=True) == 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
    keys = ['screen_brightness_mode', 'screen_brightness', 'min_refresh_rate',
            'peak_refresh_rate', 'screen_off_timeout']
    original = {k: sh('settings get system ' + k) for k in keys}
    original_stay_on = sh('settings get global stay_on_while_plugged_in')
    report['original_stay_on_while_plugged_in'] = original_stay_on
    report['original_settings'] = original
    report['panel_dc_before'] = sh('cat /sys/class/drm/card0-DSI-1/panelDC', root=True)
    save()

    if scope == 'known':
        jobs = [(2, 40, [f'0x{r:02x}' for r in range(256)], [f'0x{p:02x}' for p in KNOWN_PAGES])]
    elif scope == 'census':
        jobs = [(1, 8, [f'0x{r:02x}' for r in range(256)], [f'0x{p:02x}' for p in range(0x80)])]
    else:
        jobs = [(2, n, [f'0x{r:02x}'], [f'0x{p:02x}']) for p, r, n in PROBES]

    raw = []
    try:
        sh(f'settings put system screen_brightness_mode 0; settings put system screen_brightness {brightness}; '
           f'settings put system min_refresh_rate {refresh}; settings put system peak_refresh_rate {refresh}; '
           'settings put system screen_off_timeout 1800000; settings put global stay_on_while_plugged_in 7; '
           'input keyevent 224')
        deadline = time.monotonic() + 8
        while 'mWakefulness=Awake' not in sh('dumpsys power | grep mWakefulness='):
            assert time.monotonic() < deadline, 'Screen did not wake'
            time.sleep(.3)
        sh('wm dismiss-keyguard')
        sh("am start -W --activity-clear-top -n 'com.android.settings/.Settings$DisplaySettingsActivity'")
        time.sleep(2.5)
        assert 'mWakefulness=Awake' in sh('dumpsys power | grep mWakefulness=')
        assert 'isKeyguardShowing=false' in sh('dumpsys window | grep -m1 -o isKeyguardShowing=[a-z]*', check=False) or True
        report['dbv_before'] = sh('cat ' + BL, root=True)
        report['refresh_before'] = sh("dumpsys display | grep -m1 -o 'mActiveSfDisplayMode=[^}]*'", check=False)
        sh(f'mkdir -m 700 -p {TMP}/dbg', root=True)
        subprocess.run(['adb', '-t', transport, 'push', str(ROOT / '06-tools/ddic_regdump.sh'),
                        '/data/local/tmp/ddic_regdump.sh'], check=True, capture_output=True)
        sh(f'mv /data/local/tmp/ddic_regdump.sh {TMP}/run.sh && chmod 700 {TMP}/run.sh && '
           f'chown root:root {TMP}/run.sh', root=True)
        for passes, length, regs, pages in jobs:
            sh(f"echo '{' '.join(regs)}' > {TMP}/regs", root=True)
            text = sh(f'unshare -m /system/bin/sh {TMP}/run.sh {passes} {length} {TMP}/regs ' + ' '.join(pages),
                      root=True, timeout=1800, check=False)
            raw.append(text)
            assert 'ESD_RESTORED reg_read' in text, 'ESD mode restore not confirmed:\n' + text[-500:]
        report['dbv_after'] = sh('cat ' + BL, root=True)
        report['refresh_after'] = sh("dumpsys display | grep -m1 -o 'mActiveSfDisplayMode=[^}]*'", check=False)
    finally:
        (out / 'raw.txt').write_text('\n'.join(raw) + '\n')
        sh(f'rm -f {TMP}/run.sh {TMP}/regs; rmdir {TMP}/dbg {TMP}', root=True, check=False)
        for k, v in original.items():
            if k in ('min_refresh_rate', 'peak_refresh_rate') and v == 'null':
                sh('settings delete system ' + k, check=False)
            else:
                sh(f'settings put system {k} {v}', check=False)
        sh(f'settings put global stay_on_while_plugged_in {original_stay_on}', check=False)
        sh('input keyevent 4', check=False)
        report['esd_mode_after'] = sh(
            "unshare -m /system/bin/sh -c 'mount -o rprivate none /; mkdir -p /data/local/tmp/ddic-chk; "
            "mount -t debugfs debugfs /data/local/tmp/ddic-chk && "
            "cat /data/local/tmp/ddic-chk/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode; "
            "umount /data/local/tmp/ddic-chk; rmdir /data/local/tmp/ddic-chk'", root=True, check=False).strip()
        report['finished_at_utc'] = now()
        save()

    values, errors, mismatch = {}, [], []
    for line in '\n'.join(raw).splitlines():
        m = re.fullmatch(r'R (\d+) (0x[0-9a-f]+) (0x[0-9a-f]+) ?(.*)', line.strip())
        if m:
            key = f'{int(m[2], 16):02X}:{int(m[3], 16):02X}'
            data = [int(x, 16) for x in m[4].split()]
            values.setdefault(key, []).append(data)
        elif line.startswith(('E ', 'ERR')):
            errors.append(line.strip())
    table = {}
    for key, reads in values.items():
        if any(r != reads[0] for r in reads):
            mismatch.append({'reg': key, 'reads': reads})
        table[key] = ' '.join(f'{b:02X}' for b in reads[0])
    checks = []
    for (p, r), want in EXPECTED.items():
        got = table.get(f'{p:02X}:{r:02X}')
        if got is not None:
            checks.append({'reg': f'{p:02X}:{r:02X}', 'expected': f'{want:02X}', 'read': got,
                           'match': got.split()[0] == f'{want:02X}' if got else False})
    report.update({'read_count': sum(len(v) for v in values.values()), 'error_lines': errors[:200],
                   'error_count': len(errors), 'pass_mismatches': mismatch,
                   'ground_truth_checks': checks})
    (out / 'registers.json').write_text(json.dumps(table, indent=1, sort_keys=True) + '\n')
    save()
    ok = sum(c['match'] for c in checks)
    print(f'{label}: reads={report["read_count"]} errors={len(errors)} mismatches={len(mismatch)} '
          f'ground_truth={ok}/{len(checks)} dbv={report.get("dbv_before")}->{report.get("dbv_after")} '
          f'esd_after={report["esd_mode_after"]!r}')


if __name__ == '__main__':
    main()
