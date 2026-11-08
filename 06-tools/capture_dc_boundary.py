#!/usr/bin/env python3
"""Capture a stock brightness-boundary trial using prepared Pacman Camera2.

Usage: python3 06-tools/capture_dc_boundary.py TARGET_TRANSPORT CAMERA_TRANSPORT [--exact-dbv]
Requires the saved preparation/restore state; never selects an arbitrary ADB device.
"""
import json
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET, CAMERA, *options = sys.argv[1:]
assert options in ([], ['--exact-dbv']), 'Only the documented exact-DBV variant is supported'
EXACT = bool(options)
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode') / (
    'pacman-exact-20261106' if EXACT else 'pacman-camera-20261106')
SESSION = ROOT / ('artifacts/pacman_exact_session_20261106.json' if EXACT
                  else 'artifacts/pacman_camera_session_20261106.json')
OUTPUT = ROOT / ('artifacts/pacman_exact_capture_20261106.json' if EXACT
                 else 'artifacts/pacman_boundary_capture_20261106.json')
assert TARGET != CAMERA and not OUTPUT.exists(), 'Distinct transports; no automatic repeat'
session = json.loads(SESSION.read_text())
assert session['target_restore_required'] and session['screen_timeout_override_verified']
record = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Owner-authorized autonomous optical camera capture; stock DC OFF only',
          'phases': [], 'events': [], 'video_received': False, 'pwm_hz': 'unknown'}
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'


def now():
    return datetime.now(timezone.utc).isoformat()


def save():
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')


def sh(device, command, root=False, private_name=None):
    remote = 'su -c ' + shlex.quote(command) if root else command
    result = subprocess.run(['adb', '-t', device, 'shell', remote],
                            capture_output=True, text=True, timeout=30)
    if private_name:
        path = PRIVATE / private_name
        path.write_text(result.stdout)
        path.chmod(0o600)
    record['events'].append({'at_utc': now(), 'device': 'target' if device == TARGET else 'camera',
                             'command': remote, 'exit_code': result.returncode,
                             'stdout': '<private ' + private_name + '>' if private_name else result.stdout.strip(),
                             'stderr': result.stderr.strip()})
    save()
    if result.returncode:
        raise RuntimeError('ADB command failed: ' + command)
    return result.stdout.strip()


def camera_ui():
    sh(CAMERA, 'uiautomator dump /data/local/tmp/pwm-camera-ui.xml')
    return ET.fromstring(sh(CAMERA, 'cat /data/local/tmp/pwm-camera-ui.xml',
                            private_name='capture-camera-ui.xml'))


def tap_camera(description):
    nodes = [n for n in camera_ui().iter('node') if n.get('content-desc') == description]
    assert len(nodes) == 1, 'Expected exact camera control: ' + description
    left, top, right, bottom = map(int, re.findall(r'\d+', nodes[0].get('bounds')))
    sh(CAMERA, f'input tap {(left + right) // 2} {(top + bottom) // 2}')


def camera_metadata(label):
    text = sh(CAMERA, 'dumpsys media.camera', private_name='capture-metadata-' + label + '.txt')
    names = ('android.sensor.exposureTime', 'android.sensor.sensitivity', 'android.control.aeMode',
             'android.control.afMode', 'android.control.afState', 'android.lens.focusDistance',
             'android.sensor.rollingShutterSkew', 'android.scaler.cropRegion',
             'android.control.videoStabilizationMode', 'android.sensor.frameDuration')
    values = {name: [v.strip() for v in re.findall(re.escape(name) + r'[^\n]*\n\s*\[([^\]]+)\]', text)[:2]]
              for name in names}
    assert values['android.sensor.exposureTime'] == ['100000', '100000'], values
    assert values['android.sensor.sensitivity'] == ['6400', '6400'], values
    assert values['android.control.aeMode'] == ['OFF', 'OFF'], values
    record.setdefault('camera_metadata', {})[label] = values
    save()


def wait_target(command, expected):
    deadline = time.monotonic() + 6
    while True:
        if sh(TARGET, command, root=True) == expected:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Target state did not settle: ' + command)
        time.sleep(.2)


target_verified = camera_verified = start_attempted = logger_changed = False
try:
    assert sh(TARGET, 'getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; getenforce').splitlines() == [
        'XT2611-1', 'W3WWS36.65-64-4-1', '_b', 'Enforcing']
    target_verified = True
    assert sh(CAMERA, 'getprop ro.product.device') == 'PacmanPro'
    camera_verified = True
    assert sh(TARGET, 'cat ' + CON + 'panelDC', root=True) == '0'
    assert sh(TARGET, 'cat ' + CON + 'mipi_cmd_log_en', root=True).endswith(': 0')
    assert sh(TARGET, 'settings get system screen_brightness_mode') == '0'
    for key in ('min_refresh_rate', 'peak_refresh_rate'):
        assert float(sh(TARGET, 'settings get system ' + key)) == 120
    if EXACT:
        sh(TARGET, "printf '%s\\n' '<6>PWM_EXACT_CAMERA_BEGIN' > /dev/kmsg", root=True)
        logger_changed = True
        sh(TARGET, "printf '1\\n' > " + CON + 'mipi_cmd_log_en', root=True)
    sh(TARGET, 'input keyevent 224')
    wait_target('cat ' + BL + 'bl_power', '0')
    wait_target("dumpsys window policy | grep -F 'screenState='", 'screenState=SCREEN_STATE_ON')
    wait_target("dumpsys window policy | grep -F 'interactiveState='",
                'interactiveState=INTERACTIVE_STATE_AWAKE')
    sh(TARGET, 'wm dismiss-keyguard')
    wait_target("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
    component = shlex.quote('com.android.settings/.Settings$DisplaySettingsActivity')
    sh(TARGET, 'am start -W --activity-clear-top -n ' + component)
    policy = sh(TARGET, 'dumpsys window policy', private_name='capture-window-policy.txt')
    assert 'mIsShowing=false' in policy, 'Keyguard must be dismissed before the optical hold'
    display = sh(TARGET, 'dumpsys display', private_name='capture-target-display.txt')
    mode = re.search(r'mActiveSfDisplayMode=([^\n]+)', display)
    assert mode and re.search(r'peakRefreshRate=120\.', mode[1])
    camera_metadata('before')
    record['record_button_before_utc'] = now()
    record['media_since_epoch'] = int(time.time()) - 2
    start_attempted = True
    tap_camera('Start recording video')
    record['record_button_after_utc'] = now()
    assert any(n.get('content-desc') == 'Stop recording video' for n in camera_ui().iter('node'))
    camera_metadata('recording-start')
    levels = (3600, 3601, 3602, 3601, 3600) if EXACT else (52, 53, 52, 53)
    for index, level in enumerate(levels, 1):
        expected = level if EXACT else (3584 if level == 52 else 3646)
        if EXACT:
            sh(TARGET, f"printf '%s\\n' '<6>PWM_EXACT_CAMERA_{index}_{level}' > /dev/kmsg", root=True)
            sh(TARGET, f"printf '%s\\n' '{level}' > " + BL + 'brightness', root=True)
        else:
            sh(TARGET, f'input keyevent 224; settings put system screen_brightness {level}')
        wait_target('cat ' + BL + 'brightness', str(expected))
        assert sh(TARGET, 'cat ' + CON + 'panelDC', root=True) == '0'
        phase = {'index': index, 'brightness': level, 'dbv': expected, 'hold_start_utc': now(),
                 'setter': 'backlight_sysfs' if EXACT else 'android_settings'}
        record['phases'].append(phase)
        save()
        print(json.dumps(phase), flush=True)
        time.sleep(5 if EXACT else 8)  # Stable optical interval, not background-job polling.
        phase['hold_end_utc'] = now()
        phase['dbv_at_end'] = int(sh(TARGET, 'cat ' + BL + 'brightness', root=True))
        assert phase['dbv_at_end'] == expected
        camera_metadata('phase-' + str(index))
    record['exact_holds_completed' if EXACT else 'four_holds_completed'] = True
    if EXACT:
        sh(TARGET, "printf '%s\\n' '<6>PWM_EXACT_CAMERA_END' > /dev/kmsg", root=True)
        sh(TARGET, 'dmesg', root=True, private_name='capture-kernel.txt')
except Exception as error:
    record['error'] = type(error).__name__ + ': ' + str(error)
finally:
    cleanup_errors = []
    if logger_changed:
        try:
            sh(TARGET, "printf '0\\n' > " + CON + 'mipi_cmd_log_en', root=True)
            assert sh(TARGET, 'cat ' + CON + 'mipi_cmd_log_en', root=True).endswith(': 0')
            record['logger_restored'] = True
        except Exception as error:
            cleanup_errors.append('Logger restore: ' + str(error))
    if camera_verified and start_attempted:
        try:
            if any(n.get('content-desc') == 'Stop recording video' for n in camera_ui().iter('node')):
                tap_camera('Stop recording video')
            assert any(n.get('content-desc') == 'Start recording video' for n in camera_ui().iter('node'))
            record['camera_stopped_verified'] = True
        except Exception as error:
            cleanup_errors.append('Camera stop: ' + str(error))
    if target_verified:
        before = session['target_before']
        for key in ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode'):
            try:
                sh(TARGET, 'settings delete system ' + key if before[key] == 'null'
                   else 'settings put system ' + key + ' ' + shlex.quote(before[key]))
            except Exception as error:
                cleanup_errors.append(key + ': ' + str(error))
        try:
            if before['bl_power'] == '4':
                sh(TARGET, 'input keyevent 223')
            wait_target('cat ' + BL + 'bl_power', before['bl_power'])
            after = {k: sh(TARGET, 'settings get system ' + k) for k in before if k != 'bl_power'}
            after['dc'] = sh(TARGET, 'cat ' + CON + 'panelDC', root=True)
            after['selinux'] = sh(TARGET, 'getenforce')
            assert all(after[k] == before[k] for k in before if k not in ('bl_power', 'screen_brightness'))
            assert after['dc'] == '0' and after['selinux'] == 'Enforcing'
            if before['screen_brightness_mode'] == '0':
                assert after['screen_brightness'] == before['screen_brightness']
            record['target_restored'] = after
            session['target_restore_required'] = False
        except Exception as error:
            cleanup_errors.append('Target restore verification: ' + str(error))
    record['cleanup_errors'] = cleanup_errors
    record['finished_at_utc'] = now()
    SESSION.write_text(json.dumps(session, ensure_ascii=False, indent=2) + '\n')
    save()
print(json.dumps({k: v for k, v in record.items() if k != 'events'}, indent=2), flush=True)
if record.get('error') or cleanup_errors:
    raise SystemExit(1)
