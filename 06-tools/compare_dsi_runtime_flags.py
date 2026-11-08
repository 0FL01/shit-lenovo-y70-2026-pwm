#!/usr/bin/env python3
"""One-shot stock raw/UI transport comparison; no camera or custom panel bytes."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/dsi_runtime_flags_20261106.json'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-runtime-flags-20261106')
TMP = '/data/local/tmp/pwm-flags-20261106'
TRACE = '/sys/kernel/tracing/instances/pwm_cmp'
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
MODULE_SHA = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
# Offsets verified against this exact target ELF, not a public/stable kernel ABI.
PROBES = {
    'cmp_ctrl': 'p:pwm_cmp/cmp_ctrl msm_drm:dsi_ctrl_cmd_transfer ctrl=$arg1:x64 cmd=$arg2:x64 channel=+0($arg2):u8 type=+1($arg2):x8 msg_flags=+2($arg2):x16 len=+8($arg2):u64 rx_len=+0x18($arg2):u64 last=+0x28($arg2):u8 wait_ms=+0x2c($arg2):u32 route=+0x30($arg2):u32 ctrl_flags=+0x34($arg2):x32 flush=$arg3:u8 cmd_len=+0xae8($arg1):u32 secure=+0xaf8($arg1):u8',
    'cmp_flags': 'p:pwm_cmp/cmp_flags msm_drm:dsi_display_set_cmd_tx_ctrl_flags display=$arg1:x64 cmd=$arg2:x64 in_ctrl_flags=+0x34($arg2):x32 qwait=+0x678($arg1):u8 esync=+0x420($arg1):u8 enabled=+0x798($arg1):u8 nctrl=+0xb8($arg1):u32 panel_mode=+0x548(+0x120($arg1)):u32',
    'cmp_prepare': 'p:pwm_cmp/cmp_prepare msm_drm:dsi_ctrl_transfer_prepare ctrl=$arg1:x64 flags=$arg2:x32 cmd_len=+0xae8($arg1):u32 post_queued=+0xb28($arg1):u8',
    'cmp_unprepare': 'p:pwm_cmp/cmp_unprepare msm_drm:dsi_ctrl_transfer_unprepare ctrl=$arg1:x64 flags=$arg2:x32 cmd_len=+0xae8($arg1):u32',
    'cmp_return': 'r:pwm_cmp/cmp_return msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32',
    'cmp_raw': 'p:pwm_cmp/cmp_raw msm_drm:dsi_display_cmd_transfer pending=+0x694($arg2):u32 length=$arg4:u32 flags=+3($arg3):u8',
    'cmp_raw_return': 'r:pwm_cmp/cmp_raw_return msm_drm:dsi_display_cmd_transfer rc=$retval:s32',
}


def main():
    assert len(sys.argv) == 2, 'Usage: compare_dsi_runtime_flags.py TARGET_TRANSPORT'
    transport = int(sys.argv[1])
    assert not OUT.exists()
    parse = runpy.run_path(str(ROOT / '06-tools/inspect_cn_dtbo.py'))['packets']
    programs = {mode: (ROOT / 'artifacts/device_tree/selected_boe_v4' / ('qcom,mdss-dsi-dc-' + mode + '-command')).read_bytes() for mode in ('on', 'off')}
    ranges = [(0, 253), (253, 500), (500, 754), (754, 864), (864, 875)]
    PRIVATE.mkdir(mode=0o700)
    chunks = PRIVATE / 'chunks'
    chunks.mkdir(mode=0o700)
    for mode, data in programs.items():
        assert len(data) == 875 and len(parse(data)) == 75
        assert [bytes.fromhex(p['header_hex'])[3] for p in parse(data)] == [64] * 74 + [0]
        for i, (start, end) in enumerate(ranges):
            assert parse(data[start:end]) and end - start < 256
            path = chunks / f'{mode}_{i}.txt'
            path.write_text(' '.join(f'0x{x:02x}' for x in data[start:end]))
            path.chmod(0o600)
    r = {'scope': 'Read-only runtime probes around unchanged stock raw ON/OFF and native UI ON/OFF; no custom profile/camera/flash',
         'started_at_utc': datetime.now(timezone.utc).isoformat(), 'stages': [], 'events': [], 'pwm_hz': 'unknown'}
    probes = []
    instance = temporary = prepared = logger = raw_uncertain = raw_on = ui_touched = False
    raw_count = 0

    def now():
        return datetime.now(timezone.utc).isoformat()

    def save():
        OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')

    def sh(command, root=False, private=None):
        remote = 'su -c ' + shlex.quote(command) if root else command
        p = subprocess.run(['adb', '-t', str(transport), 'shell', remote], capture_output=True, text=True, timeout=30)
        if private:
            path = PRIVATE / private
            path.write_text(p.stdout)
            path.chmod(0o600)
        r['events'].append({'at_utc': now(), 'command': command, 'root': root, 'exit_code': p.returncode,
                            'stdout': '<private ' + private + '>' if private else p.stdout.strip(), 'stderr': p.stderr.strip()})
        save()
        if p.returncode:
            raise RuntimeError('Command failed: ' + command)
        return p.stdout.strip()

    def wait(command, wanted, seconds=6):
        deadline = time.monotonic() + seconds
        while sh(command, True) != wanted:
            if time.monotonic() >= deadline:
                raise RuntimeError('State timeout: ' + command)
            time.sleep(.15)

    def identity():
        assert sh('getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce').splitlines() == [
            'XT2611-1', 'W3WWS36.65-64-4-1', '_b', '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k', 'Enforcing']
        assert sh('id', True).startswith('uid=0(')
        assert sh('cat ' + CON + 'panelName', True) == 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
        assert sh('sha256sum /vendor/lib/modules/msm_drm.ko', True).split()[0] == MODULE_SHA

    def dc(value):
        for _ in range(3):
            text = sh(f'uiautomator dump {TMP}/ui.xml >/dev/null && cat {TMP}/ui.xml', private='ui.xml')
            tree = ET.fromstring(text)
            parents = {c: p for p in tree.iter() for c in p}
            labels = [n for n in tree.iter('node') if n.get('text') == 'Flicker prevention' and n.get('package') == 'com.android.settings']
            if len(labels) == 1:
                row = labels[0]
                while row.get('clickable') != 'true':
                    row = parents[row]
                switches = [n for n in row.iter('node') if n.get('checkable') == 'true']
                assert len(switches) == 1
                if (switches[0].get('checked') == 'true') != bool(value):
                    a, b, c, d = map(int, re.findall(r'\d+', row.get('bounds')))
                    sh(f'input tap {(a+c)//2} {(b+d)//2}')
                wait('cat ' + CON + 'panelDC', str(value))
                assert 'value=' + str(value) in sh('content call --uri content://com.motorola.android.providers.settings/global --method GET_global --arg display_dc_mode_enabled')
                return
            if any(n.get('text') == 'Select USB mode' for n in tree.iter('node')):
                sh('input keyevent 4')
            else:
                sh('input swipe 720 2780 720 850 400')
        raise RuntimeError('Native Flicker prevention control unavailable')

    def mark(text):
        sh("printf '%s\\n' " + shlex.quote(text) + ' > ' + TRACE + '/trace_marker; ' +
           "printf '%s\\n' " + shlex.quote('<6>' + text) + ' > /dev/kmsg', True)

    def trace(label):
        text = sh('cat ' + TRACE + '/trace', True, label + '-trace.txt')
        assert 'LOST' not in text and '(fault)' not in text.lower() and not re.search(r'\brc=-\d+', text)
        return text

    identity()
    assert sh('cat ' + CON + 'panelDC', True) == '0'
    assert sh('cat ' + CON + 'mipi_cmd_log_en', True).endswith(': 0')
    sh(f'test ! -e {TMP} && test ! -e {TRACE} && ! grep -q pwm_cmp/ /sys/kernel/tracing/kprobe_events', True)
    keys = ('screen_brightness', 'screen_brightness_mode', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout')
    before = {k: sh('settings get system ' + k) for k in keys}
    before['bl_power'] = sh('cat ' + BL + 'bl_power', True)
    assert before['bl_power'] in ('0', '4')
    r['before'] = before
    save()
    try:
        sh(f'mkdir -m 700 {TMP}; mkdir {TMP}/debugfs')
        temporary = True
        subprocess.run(['adb', '-t', str(transport), 'push', str(chunks), TMP + '/'], check=True, capture_output=True, timeout=30)
        for path in chunks.iterdir():
            assert sh('sha256sum ' + TMP + '/chunks/' + path.name).split()[0] == hashlib.sha256(path.read_bytes()).hexdigest()
        prepared = True
        sh('settings put system screen_brightness_mode 0; settings put system screen_brightness 52; settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; settings put system screen_off_timeout 600000; input keyevent 224')
        wait("dumpsys window policy | grep -F 'screenState='", 'screenState=SCREEN_STATE_ON')
        wait("dumpsys window policy | grep -F 'interactiveState='", 'interactiveState=INTERACTIVE_STATE_AWAKE')
        sh('wm dismiss-keyguard')
        wait("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
        sh('am start -W --activity-clear-top -n ' + shlex.quote('com.android.settings/.Settings$DisplaySettingsActivity'))
        dc(0)
        sh("printf '3600\\n' > " + BL + 'brightness', True)
        wait('cat ' + BL + 'brightness', '3600')
        assert re.search(r'mActiveSfDisplayMode=[^\n]*peakRefreshRate=120\.', sh('dumpsys display', private='display.txt'))
        sh('mkdir ' + TRACE, True)
        instance = True
        sh('printf 0 > ' + TRACE + '/tracing_on; printf mono > ' + TRACE + '/trace_clock', True)
        for name, spec in PROBES.items():
            sh("printf '%s\\n' " + shlex.quote(spec) + ' >> /sys/kernel/tracing/kprobe_events', True)
            probes.append(name)
        sh(f'printf 1 > {TRACE}/events/pwm_cmp/enable; printf 1 > {TRACE}/tracing_on', True)
        logger = True
        sh('printf 1 > ' + CON + 'mipi_cmd_log_en', True)
        for label, mode, native_ui in [('raw_on', 'on', False), ('raw_off', 'off', False), ('ui_on', 'on', True), ('ui_off', 'off', True)]:
            stage = {'label': label, 'started_at_utc': now()}
            r['stages'].append(stage)
            mark('PWM_FLAGS_BEGIN_' + label)
            if native_ui:
                ui_touched = True
                dc(int(mode == 'on'))
            else:
                raw_on = raw_on or mode == 'on'
                for i, (start, end) in enumerate(ranges):
                    raw_uncertain = True
                    r['raw_return_required'] = True
                    save()
                    node = TMP + '/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd'
                    cmd = (f'set -e; mount -o rprivate none /; mount -t debugfs -o nosuid,nodev,noexec debugfs {TMP}/debugfs; '
                           f'test -f {node}; test -w {node}; dd if={TMP}/chunks/{mode}_{i}.txt of={node} bs=4096 count=1 conv=notrunc status=none')
                    sh('unshare -m /system/bin/sh -c ' + shlex.quote(cmd), True)
                    text = trace(label)
                    entries = re.findall(r'\bcmp_raw:.*?pending=(\d+) length=(\d+) flags=(\d+)', text)
                    returns = re.findall(r'\bcmp_raw_return:.*?rc=(-?\d+)', text)
                    assert len(entries) == len(returns) == raw_count + 1
                    assert tuple(map(int, entries[-1])) == (start, end-start, 64 if i < 4 else 0) and returns[-1] == '0'
                    raw_count += 1
            sh("printf '3600\\n' > " + BL + 'brightness', True)
            wait('cat ' + BL + 'brightness', '3600')
            time.sleep(.5)  # Observe asynchronous completion before ending this trace window.
            assert sh('cat ' + BL + 'bl_power', True) == '0'
            assert sh('cat ' + CON + 'panelDC', True) == str(int(native_ui and mode == 'on'))
            mark('PWM_FLAGS_END_' + label)
            kernel = sh('dmesg', True, label + '-kernel.txt')
            section = kernel[kernel.index('PWM_FLAGS_BEGIN_' + label):kernel.index('PWM_FLAGS_END_' + label)]
            assert 'Command transfer failed' not in section
            writes = re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)', section)
            observed = [(int(n), int(t, 16), m, bytes.fromhex(p)) for n, t, m, p in writes]
            expected = [(len(bytes.fromhex(p['payload_hex'])), bytes.fromhex(p['header_hex'])[0], 'hs', bytes.fromhex(p['payload_hex'])) for p in parse(programs[mode])]
            assert observed == expected + [(3, 0x39, 'hs', bytes.fromhex('51 0e 10'))]
            trace(label)
            stage.update(table_packets_matched=75, post_table_dbv_matched=True, finished_at_utc=now())
            raw_uncertain = False
            if not native_ui and mode == 'off':
                raw_on = False
                r['raw_return_required'] = False
            save()
            print(json.dumps({'stage': label, 'native_packets': 76}), flush=True)
        profile = sh('cat /sys/kernel/tracing/kprobe_profile', True, 'probe-profile.txt')
        r['probe_counts'] = {}
        for name in PROBES:
            rows = re.findall(r'^\s*' + name + r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
            assert len(rows) == 1 and int(rows[0][1]) == 0, (name, rows)
            r['probe_counts'][name] = {'hits': int(rows[0][0]), 'misses': int(rows[0][1])}
        r['comparison_captured'] = True
    except BaseException as error:
        r['error'] = type(error).__name__ + ': ' + str(error)
        save()
        if raw_uncertain or raw_on:
            try:
                subprocess.run(['adb', '-t', str(transport), 'reboot'], check=True, capture_output=True, timeout=15)
                subprocess.run(['adb', '-d', 'wait-for-device'], check=True, capture_output=True, timeout=75)
                rows = subprocess.check_output(['adb', 'devices', '-l'], text=True).splitlines()
                ids = [int(re.search(r'\btransport_id:(\d+)', x)[1]) for x in rows if len(x.split()) > 1 and x.split()[1] == 'device' and 'device:avr' in x.split()]
                assert len(ids) == 1
                transport = ids[0]
                wait('getprop sys.boot_completed', '1', seconds=60)
                identity()
                assert sh('cat ' + CON + 'panelDC', True) == '0'
                instance = logger = raw_uncertain = raw_on = False
                probes.clear()
                r.update(recovery_reboot_verified=True, raw_return_required=False)
            except Exception as recovery_error:
                r['recovery_error'] = str(recovery_error)
    finally:
        errors = []
        if not r.get('recovery_error'):
            if instance:
                try:
                    sh(f'printf 0 > {TRACE}/tracing_on', True)
                    sh('cat ' + TRACE + '/trace', True, 'trace-final.txt')
                    sh(f'printf 0 > {TRACE}/events/pwm_cmp/enable; rmdir {TRACE}', True)
                except Exception as error:
                    errors.append('Trace: ' + str(error))
            for name in reversed(probes):
                try:
                    sh("printf '%s\\n' " + shlex.quote('-:pwm_cmp/' + name) + ' >> /sys/kernel/tracing/kprobe_events', True)
                except Exception as error:
                    errors.append('Probe: ' + str(error))
            if logger:
                try:
                    sh('printf 0 > ' + CON + 'mipi_cmd_log_en', True)
                except Exception as error:
                    errors.append('Logger: ' + str(error))
            if prepared:
                try:
                    if ui_touched:
                        dc(0)
                    for k in ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode'):
                        sh('settings delete system ' + k if before[k] == 'null' else 'settings put system ' + k + ' ' + shlex.quote(before[k]))
                    if before['bl_power'] == '4':
                        sh('input keyevent 223')
                    wait('cat ' + BL + 'bl_power', before['bl_power'])
                    after = {k: sh('settings get system ' + k) for k in keys}
                    after['dc'] = sh('cat ' + CON + 'panelDC', True)
                    after['logger'] = sh('cat ' + CON + 'mipi_cmd_log_en', True)
                    after['selinux'] = sh('getenforce')
                    assert all(after[k] == before[k] for k in keys if k != 'screen_brightness')
                    if before['screen_brightness_mode'] == '0':
                        assert after['screen_brightness'] == before['screen_brightness']
                    assert after['dc'] == '0' and after['logger'].endswith(': 0') and after['selinux'] == 'Enforcing'
                    r.update(target_restored=True, after=after)
                except Exception as error:
                    errors.append('Target restore: ' + str(error))
            if temporary:
                try:
                    sh('rm -f ' + TMP + '/ui.xml ' + ' '.join(TMP + '/chunks/' + p.name for p in chunks.iterdir()) + f'; rmdir {TMP}/chunks {TMP}/debugfs {TMP}')
                    r['temporary_device_files_removed'] = True
                except Exception as error:
                    errors.append('Temporary files: ' + str(error))
        r.update(cleanup_errors=errors, finished_at_utc=now())
        save()
    print(json.dumps({k: v for k, v in r.items() if k != 'events'}, indent=2), flush=True)
    if r.get('error') or r.get('recovery_error') or r['cleanup_errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
