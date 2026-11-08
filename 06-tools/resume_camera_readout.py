#!/usr/bin/env python3
"""Finish the recorded 720p -> 4K -> 720p experiment, without repeating A1."""
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
OUT = ROOT / 'artifacts/pacman_readout_capture_20261106.json'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/pacman-readout-20261106')
TARGET, CAMERA = sys.argv[1:]
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
r = json.loads(OUT.read_text())
assert [c['label'] for c in r['clips']] == ['A1'] and r['target_restored']
assert 'resumed_at_utc' not in r, 'No automatic repeat'
r['first_attempt'] = {k: r.pop(k) for k in ('error', 'cleanup_errors', 'finished_at_utc')}
r['resumed_at_utc'] = datetime.now(timezone.utc).isoformat()


def save():
    OUT.write_text(json.dumps(r, indent=2) + '\n')


def sh(device, command, root=False, name=None):
    remote = 'su -c ' + shlex.quote(command) if root else command
    p = subprocess.run(['adb', '-t', device, 'shell', remote], capture_output=True,
                       text=True, timeout=25)
    if name:
        path = PRIVATE / name
        path.write_text(p.stdout)
        path.chmod(0o600)
    r['events'].append({'at_utc': datetime.now(timezone.utc).isoformat(),
                        'device': 'target' if device == TARGET else 'camera',
                        'command': remote, 'exit_code': p.returncode,
                        'stdout': '<private ' + name + '>' if name else p.stdout.strip(),
                        'stderr': p.stderr.strip()})
    save()
    if p.returncode:
        raise RuntimeError('Command failed: ' + command)
    return p.stdout.strip()


def ui():
    return ET.fromstring(sh(CAMERA, 'uiautomator dump /data/local/tmp/pwm-readout-camera.xml '
                           '>/dev/null && cat /data/local/tmp/pwm-readout-camera.xml',
                           name='resume-camera-ui.xml'))


def tap(label, tree=None):
    nodes = [n for n in (ui() if tree is None else tree).iter('node')
             if n.get('content-desc') == label]
    assert len(nodes) == 1, label
    a, b, c, d = map(int, re.findall(r'\d+', nodes[0].get('bounds')))
    sh(CAMERA, f'input tap {(a+c)//2} {(b+d)//2}')


def resolution(width, height):
    tree = ui()
    if not any(n.get('text') == 'Video resolution:' for n in tree.iter('node')):
        tap('Popup settings', tree)
        tree = ui()
    previous = None
    while True:
        matches = [re.match(r'^(\d+)x(\d+)\b', n.get('text', '')) for n in tree.iter('node')]
        sizes = [tuple(map(int, m.groups())) for m in matches if m]
        assert len(sizes) == 1, sizes
        current = sizes[0]
        r.setdefault('resolution_selection', []).append(list(current))
        save()
        if current == (width, height):
            tap('Popup settings', tree)
            return
        distance = abs(current[0] * current[1] - width * height)
        assert previous is None or distance < previous, 'Resolution menu did not approach requested size'
        previous = distance
        tap('Next Video resolution' if current[0] * current[1] < width * height
            else 'Previous Video resolution', tree)
        tree = ui()


def wait(command, expected):
    deadline = time.monotonic() + 6
    while sh(TARGET, command, root=True) != expected:
        if time.monotonic() >= deadline:
            raise RuntimeError('State timeout: ' + command)
        time.sleep(.15)


def metadata(label):
    text = sh(CAMERA, 'dumpsys media.camera', name=label + '.txt')
    names = tuple(r['clips'][0]['start_metadata'])
    values = {k: [v.strip() for v in re.findall(re.escape(k) + r'[^\n]*\n\s*\[([^\]]+)\]', text)[:2]]
              for k in names}
    for key, expected in [('android.sensor.exposureTime', '100000'),
                          ('android.sensor.sensitivity', '6400'), ('android.control.aeMode', 'OFF'),
                          ('android.control.afMode', 'OFF')]:
        assert values[key] == [expected, expected], (key, values[key])
    assert len(values['android.lens.focusDistance']) == 2
    assert all(abs(float(v) - 9.11752701) < .001 for v in values['android.lens.focusDistance'])
    return values


assert TARGET != CAMERA
assert sh(TARGET, 'getprop ro.boot.hardware.sku; getprop ro.build.display.id; getenforce').splitlines() == [
    'XT2611-1', 'W3WWS36.65-64-4-1', 'Enforcing']
assert sh(CAMERA, 'getprop ro.product.device') == 'PacmanPro'
assert sh(TARGET, 'cat ' + CON + 'panelDC', root=True) == '0'
keys = ('screen_brightness', 'screen_brightness_mode', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout')
before = {k: sh(TARGET, 'settings get system ' + k) for k in keys}
before['bl_power'] = sh(TARGET, 'cat ' + BL + 'bl_power', root=True)
r['resume_before'] = before
r['target_restored'] = False
save()
recording = False
try:
    sh(TARGET, 'settings put system screen_brightness_mode 0; settings put system screen_brightness 52; '
       'settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; '
       'settings put system screen_off_timeout 600000; input keyevent 224')
    wait("dumpsys window policy | grep -F 'screenState='", 'screenState=SCREEN_STATE_ON')
    wait("dumpsys window policy | grep -F 'interactiveState='", 'interactiveState=INTERACTIVE_STATE_AWAKE')
    sh(TARGET, 'wm dismiss-keyguard')
    wait("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
    sh(TARGET, 'am start -W --activity-clear-top -n ' + shlex.quote('com.android.settings/.Settings$DisplaySettingsActivity'))
    wait('cat ' + BL + 'brightness', '3584')
    sh(TARGET, "printf '3600\\n' > " + BL + 'brightness', root=True)
    wait('cat ' + BL + 'brightness', '3600')
    display = sh(TARGET, 'dumpsys display', name='resume-target-display.txt')
    mode = re.search(r'mActiveSfDisplayMode=([^\n]+)', display)
    assert mode and 'peakRefreshRate=120.' in mode[1]
    for label, width, height in [('B', 3840, 2160), ('A2', 1280, 720)]:
        resolution(width, height)
        assert sh(TARGET, 'cat ' + BL + 'brightness', root=True) == '3600'
        clip = {'label': label, 'requested_size': [width, height], 'media_since_epoch': int(time.time()) - 2}
        r['clips'].append(clip)
        recording = True
        tap('Start recording video')
        assert any(n.get('content-desc') == 'Stop recording video' for n in ui().iter('node'))
        clip['start_metadata'] = metadata(label + '-start')
        clip['hold_start_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print(json.dumps({'clip': label, 'skew': clip['start_metadata']['android.sensor.rollingShutterSkew']}), flush=True)
        time.sleep(7)  # Optical observation interval, not job polling.
        clip['hold_end_utc'] = datetime.now(timezone.utc).isoformat()
        clip['end_metadata'] = metadata(label + '-end')
        clip['dbv_at_end'] = sh(TARGET, 'cat ' + BL + 'brightness', root=True)
        assert clip['dbv_at_end'] == '3600' and sh(TARGET, 'cat ' + CON + 'panelDC', root=True) == '0'
        tap('Stop recording video')
        recording = False
        assert any(n.get('content-desc') == 'Start recording video' for n in ui().iter('node'))
        query = sh(CAMERA, 'content query --uri content://media/external/video/media '
                   '--projection _id:_data:_size:duration:date_added --where ' +
                   shlex.quote('date_added>=' + str(clip['media_since_epoch'])))
        rows = re.findall(r'_data=(/storage/emulated/0/DCIM/OpenCamera/VID_\d+_\d+\.mp4), _size=(\d+), duration=(\d+), date_added=(\d+)', query)
        assert len(rows) == 1, rows
        source, size, duration, _ = rows[0]
        dest = ROOT / f'artifacts/optical/pacman_readout_{label}_20261106.mp4'
        assert not dest.exists()
        p = subprocess.run(['adb', '-t', CAMERA, 'pull', source, str(dest)], capture_output=True, text=True, timeout=100)
        assert p.returncode == 0 and dest.stat().st_size == int(size)
        dest.chmod(0o600)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(dest)], text=True))
        video = next(v for v in probe['streams'] if v['codec_type'] == 'video')
        assert (video['width'], video['height']) == (width, height)
        clip.update(video=str(dest.relative_to(ROOT)), bytes=int(size), duration_ms=int(duration),
                    video_metadata={k: video.get(k) for k in ('width', 'height', 'avg_frame_rate', 'nb_frames', 'duration')})
        save()
    r['series_complete'] = True
except Exception as error:
    r['error'] = type(error).__name__ + ': ' + str(error)
finally:
    errors = []
    try:
        if recording and any(n.get('content-desc') == 'Stop recording video' for n in ui().iter('node')):
            tap('Stop recording video')
        resolution(1280, 720)
        r['camera_resolution_returned_to720p'] = True
    except Exception as error:
        errors.append('Camera return: ' + str(error))
    for key in ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode'):
        try:
            sh(TARGET, 'settings delete system ' + key if before[key] == 'null'
               else 'settings put system ' + key + ' ' + shlex.quote(before[key]))
        except Exception as error:
            errors.append(key + ': ' + str(error))
    try:
        if before['bl_power'] == '4':
            sh(TARGET, 'input keyevent 223')
        wait('cat ' + BL + 'bl_power', before['bl_power'])
        after = {k: sh(TARGET, 'settings get system ' + k) for k in keys}
        after['dc'] = sh(TARGET, 'cat ' + CON + 'panelDC', root=True)
        after['selinux'] = sh(TARGET, 'getenforce')
        assert all(after[k] == before[k] for k in keys if k != 'screen_brightness')
        assert after['dc'] == '0' and after['selinux'] == 'Enforcing'
        if before['screen_brightness_mode'] == '0':
            assert after['screen_brightness'] == before['screen_brightness']
        r['after'] = after
        r['target_restored'] = True
    except Exception as error:
        errors.append('Target restore: ' + str(error))
    r['cleanup_errors'] = errors
    r['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    save()
print(json.dumps({k: v for k, v in r.items() if k != 'events'}, indent=2), flush=True)
if r.get('error') or errors:
    raise SystemExit(1)
