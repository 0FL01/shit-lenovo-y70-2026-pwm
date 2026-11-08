#!/usr/bin/env python3
"""One-shot stock UI0/1/0 + bounded short DDIC readback, no synthetic profile."""
import json
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from run_ddic_regdump import IDENTITY, now

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/ddic_regdump_20261107/stock_latch.json'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/ddic-latch-20261107')
TMP = '/data/local/tmp/pwm-ddic-latch-20261107'
TRACE = '/sys/kernel/tracing/instances/pwm_latch'
CON = '/sys/class/drm/card0-DSI-1/'
BL = '/sys/class/backlight/panel0-backlight/'
READS = [(0x4F, r, 1) for r in (0x80, 0x81, 0x88, 0x8B, 0xC1, 0xC9, 0xD1, 0xD9)] + [
    (0x23, 0xA9, 1), (0x23, 0xAA, 1), (0x24, 0x9D, 1), (0x24, 0x9E, 1),
    (0x23, 0x80, 1), (0x53, 0x95, 2), (0, 0x52, 2)]


def reader(restore_only=False, *, mount_dir=None, reads=READS):
    # Native timeout bounds the isolated mount lifetime independently of host ADB.
    mount_dir = mount_dir or TMP + '/dbg'
    assert re.fullmatch(r'/data/local/tmp/[a-zA-Z0-9_/-]+', mount_dir)
    assert all(0 <= page <= 255 and 0 <= reg <= 255 and length in (1, 2) for page, reg, length in reads)
    text = f'''set -eu
mount -o rprivate none /
mount -t debugfs -o nosuid,nodev,noexec debugfs {mount_dir}
C={mount_dir}/dri/9800000.qcom,mdss_mdp/DSI-1
E={mount_dir}/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode
P0='0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0'
restore() {{
 s=$?; trap - EXIT
 printf '%s' "$P0" > "$C/tx_cmd" || s=31
 printf reg_read > "$E" || s=32
 m=$(tr -d '\\000' < "$E")
 printf 'ESD_RESTORED %s\\n' "$m"
 [ "$m" = reg_read ] || s=33
 umount {mount_dir} || s=34
 exit "$s"
}}
trap restore EXIT
trap 'exit 30' HUP INT TERM
'''
    if not restore_only:
        text += '''[ "$(tr -d '\\000' < "$E")" = reg_read ]
printf esd_sw_sim_success > "$E"
'''
        for page, reg, length in reads:
            text += f'''printf '%s' '0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0x{page:02X}' > "$C/tx_cmd"
printf '%s' '{length} 0x06 1 0 1 0 0 1 0x{reg:02X}' > "$C/rx_cmd"
printf '%s' "$P0" > "$C/tx_cmd"
printf 'R {page:02X}:{reg:02X} '
cat "$C/rx_cmd"
printf '\\n'
'''
    return 'timeout -k 3 15 unshare -m /system/bin/sh -c ' + shlex.quote(text)


def main():
    global OUT, PRIVATE
    assert len(sys.argv) in (3, 4), 'TARGET_TRANSPORT CAMERA_TRANSPORT [--timing-history]'
    timing_history = len(sys.argv) == 4
    if timing_history:
        assert sys.argv[3] == '--timing-history'
        OUT = ROOT / 'artifacts/ddic_regdump_20261107/stock_timing_history.json'
        PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/ddic-timing-history-20261107')
        PRIVATE.mkdir(mode=0o700)
    assert not OUT.exists(), 'One shot only'
    target_id, camera_id = map(int, sys.argv[1:3])
    assert target_id != camera_id
    marker = 'PWM_TIMING_LATCH' if timing_history else 'PWM_LATCH'
    r = {'started_at_utc': now(), 'scope': ('Stock120 ->30 ->120 ->DC ON/OFF at120; short readback and preview only' if timing_history else 'Short known-register reads and unchanged stock UI DC0/1/0 at DBV3584/120Hz'),
         'events': [], 'phases': [], 'pwm_hz': 'unknown'}

    def save():
        OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')

    def sh(command, root=False, camera=False, private=None):
        remote = 'su -c ' + shlex.quote(command) if root else command
        p = subprocess.run(['adb', '-t', str(camera_id if camera else target_id), 'shell', remote],
                           capture_output=True, text=True, timeout=30)
        if private:
            path = PRIVATE / private
            path.write_text(p.stdout)
            path.chmod(0o600)
        r['events'].append({'at_utc': now(), 'device': 'camera' if camera else 'target', 'command': command,
                            'root': root, 'exit_code': p.returncode,
                            'stdout': '<private ' + private + '>' if private else p.stdout.strip(), 'stderr': p.stderr.strip()})
        save()
        if p.returncode:
            raise RuntimeError('Command failed: ' + command[:100])
        return p.stdout.strip().replace('\x00', '')

    def wait(command, wanted):
        end = time.monotonic() + 6
        while sh(command, True) != wanted:
            if time.monotonic() >= end:
                raise RuntimeError('State timeout: ' + command)
            time.sleep(.15)

    def dc(value):
        for _ in range(3):
            text = sh(f'uiautomator dump {TMP}/ui.xml >/dev/null && cat {TMP}/ui.xml', private='target-ui.xml')
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
        raise RuntimeError('Native DC control unavailable')

    def metadata(label):
        text = sh('dumpsys media.camera', camera=True, private=label + '-camera.txt')
        keys = ('android.sensor.exposureTime', 'android.sensor.sensitivity', 'android.control.aeMode',
                'android.control.afMode', 'android.lens.focusDistance', 'android.control.videoStabilizationMode',
                'android.lens.opticalStabilizationMode', 'android.sensor.rollingShutterSkew')
        data = {k: [s.strip() for s in re.findall(re.escape(k) + r'[^\n]*\n\s*\[([^\]]+)\]', text)[:2]] for k in keys}
        assert data[keys[0]] == ['100000'] * 2 and data[keys[1]] == ['6400'] * 2
        for k in (keys[2], keys[3], keys[5], keys[6]):
            assert data[k] == ['OFF'] * 2
        assert len(data[keys[4]]) == 2 and all(abs(float(v) - 9.11752701) < .001 for v in data[keys[4]])
        return data

    def screenshot(label):
        p = subprocess.run(['adb', '-t', str(camera_id), 'exec-out', 'screencap', '-p'], capture_output=True, timeout=20)
        assert p.returncode == 0 and p.stdout.startswith(b'\x89PNG')
        path = PRIVATE / (label + '.png')
        path.write_bytes(p.stdout)
        path.chmod(0o600)
        return str(path)

    assert sh('getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce').splitlines() == IDENTITY
    assert sh('id', True).startswith('uid=0(') and sh('getprop ro.product.device', camera=True) == 'PacmanPro'
    assert sh('cat ' + CON + 'panelName', True) == 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
    assert sh('sha256sum /vendor/lib/modules/msm_drm.ko', True).split()[0] == '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
    assert sh('cat ' + CON + 'panelDC', True) == '0' and sh('cat ' + CON + 'mipi_cmd_log_en', True).endswith(': 0')
    sh(f'test ! -e {TMP} && test ! -e {TRACE} && ! grep -q pwm_latch/ /sys/kernel/tracing/kprobe_events', True)
    keys = ('screen_brightness_mode', 'screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout')
    r['before'] = {k: sh('settings get system ' + k) for k in keys}
    r['before']['stay_on'] = sh('settings get global stay_on_while_plugged_in')
    r['before']['power'] = sh('cat ' + BL + 'bl_power', True)
    assert r['before']['power'] == '0'
    r['camera_before'] = metadata('preflight')
    names = []
    temp = trace = logger = False
    try:
        sh(f'mkdir -m 700 {TMP}; mkdir -m 700 {TMP}/dbg')
        temp = True
        sh('settings put system screen_brightness_mode 0; settings put system screen_brightness 52; settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; input keyevent 224')
        wait("dumpsys window policy | grep -F 'interactiveState='", 'interactiveState=INTERACTIVE_STATE_AWAKE')
        sh('wm dismiss-keyguard')
        wait("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
        sh("am start -W --activity-clear-top -n 'com.android.settings/.Settings$DisplaySettingsActivity'")
        dc(0)
        wait('cat ' + BL + 'brightness', '3584')
        display = sh('dumpsys display', private='display.txt')
        mode = re.search(r'mActiveSfDisplayMode=([^\n]+)', display)
        assert mode and 'peakRefreshRate=120.' in mode[1]
        sh('mkdir ' + TRACE, True)
        trace = True
        for name, spec in [('ctrl', 'r:pwm_latch/ctrl msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32'),
                           ('raw', 'p:pwm_latch/raw msm_drm:dsi_display_cmd_transfer pending=+0x694($arg2):u32'),
                           ('raw_ret', 'r:pwm_latch/raw_ret msm_drm:dsi_display_cmd_transfer rc=$retval:s32')]:
            sh("printf '%s\\n' " + shlex.quote(spec) + ' >> /sys/kernel/tracing/kprobe_events', True)
            names.append(name)
        sh(f'printf mono > {TRACE}/trace_clock; printf 1 > {TRACE}/events/pwm_latch/enable; printf 1 > {TRACE}/tracing_on', True)
        logger = True
        sh('printf 1 > ' + CON + 'mipi_cmd_log_en', True)
        sh(f"printf '<6>{marker}_BEGIN\\n' > /dev/kmsg", True)
        states = [('initial', 0, 120), ('on', 1, 120), ('off', 0, 120)]
        if timing_history:
            states = [('initial120', 0, 120), ('native30', 0, 30), ('return120', 0, 120), ('dc_cycle120', 0, 120)]
        for i, (label, value, refresh) in enumerate(states, 1):
            sh(f"printf '<6>{marker}_PHASE_{i}_{value}\\n' > /dev/kmsg", True)
            if timing_history:
                sh(f'settings put system min_refresh_rate {refresh}.0; settings put system peak_refresh_rate {refresh}.0')
                if label == 'dc_cycle120':
                    dc(1)
            dc(value)
            deadline = time.monotonic() + 8
            while True:
                text = sh('dumpsys display', private=f'phase-{i}-display.txt')
                active = re.search(r'mActiveSfDisplayMode=[^\n]*?peakRefreshRate=([\d.]+)', text)
                if active and abs(float(active[1]) - refresh) < .02:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Requested stock refresh did not become active')
                time.sleep(.2)
            assert sh('cat ' + BL + 'brightness', True) == '3584'
            phase = {'index': i, 'label': label, 'dc': value, 'software_refresh': float(active[1]), 'before_read': screenshot(f'phase-{i}-before'), 'camera': metadata(f'phase-{i}')}
            r['phases'].append(phase)
            sh(f"printf '<6>{marker}_READ_{i}\\n' > /dev/kmsg", True)
            raw = sh(reader(), True, private=f'phase-{i}-reads.txt')
            assert 'ESD_RESTORED reg_read' in raw
            values = {}
            for line in raw.splitlines():
                m = re.fullmatch(r'R ([0-9A-F]{2}:[0-9A-F]{2}) (.+)', line.strip())
                if m:
                    assert m[1] not in values
                    values[m[1]] = [int(x, 16) for x in m[2].split()]
            assert len(values) == len(READS)
            for p, reg, n in READS:
                assert len(values[f'{p:02X}:{reg:02X}']) == n
            phase['registers'] = values
            phase['after_read'] = [screenshot(f'phase-{i}-after-{j}') for j in range(3)]
            kernel = sh('dmesg', True, private=f'phase-{i}-kernel.txt')
            assert 'Command transfer failed' not in kernel[kernel.index(marker + '_BEGIN'):]
            events = sh('cat ' + TRACE + '/trace', True, private=f'phase-{i}-trace.txt')
            assert 'LOST' not in events and not re.search(r'\brc=-\d+', events)
            assert all(int(x) == 0 for x in re.findall(r'\bpending=(\d+)', events))
            assert sh('cat ' + BL + 'brightness', True) == '3584' and sh('cat ' + BL + 'bl_power', True) == '0'
            save()
        r['timing_history_complete' if timing_history else 'three_states_complete'] = True
    except BaseException as error:
        r['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        errors = []
        def cleanup(label, action):
            try:
                action()
            except Exception as error:
                errors.append(label + ': ' + str(error))
        if temp:
            cleanup('Independent page0/ESD recovery', lambda: sh(reader(restore_only=True), True, private='esd-final.txt'))
        if trace:
            cleanup('Stop trace', lambda: sh(f'printf 0 > {TRACE}/tracing_on', True))
            cleanup('Save trace', lambda: sh('cat ' + TRACE + '/trace', True, private='trace-final.txt'))
            cleanup('Probe profile', lambda: sh('cat /sys/kernel/tracing/kprobe_profile', True, private='probe-profile.txt'))
            cleanup('Disable probes', lambda: sh(f'printf 0 > {TRACE}/events/pwm_latch/enable', True))
            for name in reversed(names):
                cleanup('Remove ' + name, lambda name=name: sh("printf '%s\\n' " + shlex.quote('-:pwm_latch/' + name) + ' >> /sys/kernel/tracing/kprobe_events', True))
            cleanup('Remove instance', lambda: sh('rmdir ' + TRACE, True))
        if logger:
            cleanup('Logger', lambda: sh('printf 0 > ' + CON + 'mipi_cmd_log_en', True))
        if temp:
            cleanup('Stock UI OFF', lambda: dc(0))
            for k in ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode'):
                v = r['before'][k]
                cleanup(k, lambda k=k, v=v: sh('settings delete system ' + k if v == 'null' else 'settings put system ' + k + ' ' + shlex.quote(v)))
            cleanup('Temp files', lambda: sh(f'rm -f {TMP}/ui.xml; rmdir {TMP}/dbg {TMP}', True))
        r['after'] = {k: sh('settings get system ' + k) for k in keys}
        r['after'].update(dc=sh('cat ' + CON + 'panelDC', True), logger=sh('cat ' + CON + 'mipi_cmd_log_en', True),
                          selinux=sh('getenforce'), power=sh('cat ' + BL + 'bl_power', True), stay_on=sh('settings get global stay_on_while_plugged_in'))
        r['restored'] = not errors and all(r['after'][k] == r['before'][k] for k in keys if k != 'screen_brightness') and r['after']['dc'] == '0' and r['after']['selinux'] == 'Enforcing' and r['after']['logger'].endswith(': 0') and r['after']['power'] == r['before']['power'] and r['after']['stay_on'] == r['before']['stay_on']
        if r['before']['screen_brightness_mode'] == '0':
            r['restored'] &= r['after']['screen_brightness'] == r['before']['screen_brightness']
        r.update(cleanup_errors=errors, finished_at_utc=now())
        save()
    print(json.dumps({k: v for k, v in r.items() if k not in ('events', 'phases')}, indent=2))
    if r.get('error') or not r.get('restored'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
