#!/usr/bin/env python3
"""Stock DC/base-rate/exposure references; DBV3600 and prepared Pacman camera."""
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
OUT = ROOT / 'artifacts/current_ui_dc_reference_20261106.json'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/current-ui-dc-reference-20261106')
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
TRACE = '/sys/kernel/tracing/instances/pwm_ui_ref'


def main():
    global OUT, PRIVATE, TRACE
    assert len(sys.argv) in (3, 4), 'Usage: capture_ui_dc_reference.py TARGET_TRANSPORT CAMERA_TRANSPORT [--base-rates|--exposure-notch|--exposure-notch-supported]'
    option = sys.argv[3] if len(sys.argv) == 4 else ''
    assert option in ('', '--base-rates', '--exposure-notch', '--exposure-notch-supported')
    base_rates = option == '--base-rates'
    supported_notch = option == '--exposure-notch-supported'
    notch = option in ('--exposure-notch', '--exposure-notch-supported')
    if base_rates:
        OUT = ROOT / 'artifacts/stock_base_rates_20261107/run.json'
        PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/stock-base-rates-20261107')
        TRACE = '/sys/kernel/tracing/instances/pwm_base_ref'
    if notch:
        OUT = ROOT / 'artifacts/exposure_notch_20261107/run.json'
        PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/exposure-notch-20261107')
        TRACE = '/sys/kernel/tracing/instances/pwm_notch_ref'
    if supported_notch:
        OUT = OUT.parent / 'supported/run.json'
        PRIVATE = Path(str(PRIVATE) + '-supported')
        TRACE = '/sys/kernel/tracing/instances/pwm_notch_supported'
    group = 'pwm_notch_supported' if supported_notch else 'pwm_notch_ref' if notch else 'pwm_base_ref' if base_rates else 'pwm_ui_ref'
    marker = 'PWM_NOTCH_SUPPORTED' if supported_notch else 'PWM_NOTCH_REF' if notch else 'PWM_BASE_REF' if base_rates else 'PWM_UI_REF'
    ui_path = '/data/local/tmp/' + group + '.xml'
    devices = {'target': int(sys.argv[1]), 'camera': int(sys.argv[2])}
    assert devices['target'] != devices['camera'] and not OUT.exists()
    PRIVATE.mkdir(mode=0o700)
    r = {'scope': ('Stock120/DC0/DBV3600 fixed; camera exposure-notch control at fixedISO1600, no raw replay/custom bytes'
                   if notch else 'Stock120->144->120->90->120, DC0/DBV3600; native timing trace and camera, no raw replay/custom bytes'
                   if base_rates else 'Current unchanged stock UI0/1/0, DBV3600/software120; native tracing and physical camera, no raw replay/custom bytes'),
         'started_at_utc': datetime.now(timezone.utc).isoformat(), 'phases': [], 'events': [], 'pwm_hz': 'unknown'}

    def now():
        return datetime.now(timezone.utc).isoformat()

    def save():
        OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')

    def sh(device, command, root=False, private=None):
        remote = 'su -c ' + shlex.quote(command) if root else command
        p = subprocess.run(['adb', '-t', str(devices[device]), 'shell', remote], capture_output=True, text=True, timeout=30)
        if private:
            path = PRIVATE / private
            path.write_text(p.stdout)
            path.chmod(0o600)
        r['events'].append({'at_utc': now(), 'device': device, 'command': command, 'root': root,
                            'exit_code': p.returncode, 'stdout': '<private ' + private + '>' if private else p.stdout.strip(),
                            'stderr': p.stderr.strip()})
        save()
        if p.returncode:
            raise RuntimeError('Command failed: ' + command)
        return p.stdout.strip()

    def target(command, root=False, private=None):
        return sh('target', command, root, private)

    def wait(command, wanted):
        deadline = time.monotonic() + 6
        while target(command, True) != wanted:
            if time.monotonic() >= deadline:
                raise RuntimeError('State timeout: ' + command)
            time.sleep(.15)

    def ui(device):
        text = sh(device, f'uiautomator dump {ui_path} >/dev/null && cat {ui_path}',
                  private=device + '-ui.xml')
        return ET.fromstring(text)

    def tap(device, node):
        a, b, c, d = map(int, re.findall(r'\d+', node.get('bounds')))
        sh(device, f'input tap {(a+c)//2} {(b+d)//2}')

    def camera_button(description):
        nodes = [n for n in ui('camera').iter('node') if n.get('content-desc') == description]
        assert len(nodes) == 1, description
        tap('camera', nodes[0])

    def dc(value):
        for _ in range(3):
            tree = ui('target')
            parents = {c: p for p in tree.iter() for c in p}
            labels = [n for n in tree.iter('node') if n.get('text') == 'Flicker prevention' and n.get('package') == 'com.android.settings']
            if len(labels) == 1:
                row = labels[0]
                while row.get('clickable') != 'true':
                    row = parents[row]
                switches = [n for n in row.iter('node') if n.get('checkable') == 'true']
                assert len(switches) == 1
                if (switches[0].get('checked') == 'true') != bool(value):
                    tap('target', row)
                wait('cat ' + CON + 'panelDC', str(value))
                assert 'value=' + str(value) in target('content call --uri content://com.motorola.android.providers.settings/global --method GET_global --arg display_dc_mode_enabled')
                return
            if any(n.get('text') == 'Select USB mode' for n in tree.iter('node')):
                target('input keyevent 4')
            else:
                target('input swipe 720 2780 720 850 400')
        raise RuntimeError('Native Flicker prevention control unavailable')

    def metadata(label, exposure=100000, iso=6400):
        text = sh('camera', 'dumpsys media.camera', private=label + '-camera.txt')
        keys = ('android.sensor.exposureTime', 'android.sensor.sensitivity', 'android.control.aeMode',
                'android.control.afMode', 'android.lens.focusDistance', 'android.sensor.rollingShutterSkew',
                'android.sensor.timestamp', 'android.request.frameCount', 'android.scaler.cropRegion',
                'android.control.zoomRatio', 'android.control.videoStabilizationMode', 'android.lens.opticalStabilizationMode')
        data = {k: [v.strip() for v in re.findall(re.escape(k) + r'[^\n]*\n\s*\[([^\]]+)\]', text)[:2]] for k in keys}
        assert data['android.sensor.exposureTime'] == [str(exposure)] * 2 and data['android.sensor.sensitivity'] == [str(iso)] * 2
        assert data['android.control.aeMode'] == data['android.control.afMode'] == ['OFF'] * 2
        assert len(data['android.lens.focusDistance']) == 2 and all(abs(float(v) - 9.11752701) < .001 for v in data['android.lens.focusDistance'])
        assert data['android.control.videoStabilizationMode'] == data['android.lens.opticalStabilizationMode'] == ['OFF'] * 2
        return data

    def exposure_control():
        tree = ui('camera')
        key = 'net.sourceforge.opencamera:id/exposure_time_seekbar'
        if not any(n.get('resource-id') == key for n in tree.iter('node')):
            camera_button('Exposure')
            tree = ui('camera')
        nodes = [n for n in tree.iter('node') if n.get('resource-id') == key]
        assert len(nodes) == 1
        a, b, c, d = map(int, re.findall(r'\d+', nodes[0].get('bounds')))
        assert (a, c) == (723, 1642), 'Recalibrate if camera UI geometry changes'
        return (b+d)//2

    def close_exposure():
        if any(n.get('resource-id') == 'net.sourceforge.opencamera:id/exposure_time_seekbar'
               for n in ui('camera').iter('node')):
            camera_button('Exposure')

    def iso_setting(value):
        exposure_control()
        nodes = [n for n in ui('camera').iter('node') if n.get('text') == str(value)
                 and n.get('class') == 'android.widget.Button']
        assert len(nodes) == 1, 'ISO preset unavailable'
        tap('camera', nodes[0])

    def shutter_at(x, iso):
        y = exposure_control()
        # Reset before tapping: a tap inside the current thumb can be ignored.
        sh('camera', f'input tap 758 {y}')
        if x != 758:
            sh('camera', f'input tap {x} {y}')
        time.sleep(.8)  # Bounded sensor request/result settling, not job polling.
        deadline = time.monotonic() + 6
        while True:
            text = sh('camera', 'dumpsys media.camera', private='shutter-settle.txt')
            values = [v.strip() for v in re.findall(r'android.sensor.exposureTime[^\n]*\n\s*\[([^\]]+)\]', text)[:2]]
            if len(values) == 2 and values[0] == values[1]:
                actual = int(values[0])
                metadata('shutter-verified', actual, iso)
                return actual
            if time.monotonic() >= deadline:
                raise RuntimeError('Camera request/result did not settle')
            time.sleep(.2)

    shutter_cache = {100000: 758}
    shutter_values = {100000: 100000}

    def shutter(target_ns, iso):
        if target_ns in shutter_cache:
            actual = shutter_at(shutter_cache[target_ns], iso)
            assert actual == shutter_values[target_ns], 'Repeated shutter control changed value'
        else:
            low, high = 800, 940
            candidates = []
            while low <= high:
                x = (low+high)//2
                value = shutter_at(x, iso)
                candidates.append((abs(value-target_ns), x, value))
                r.setdefault('shutter_calibration', []).append({'target_ns': target_ns, 'x': x, 'actual_ns': value})
                save()
                if abs(value-target_ns) <= .04*target_ns:
                    break
                if value < target_ns:
                    low = x+1
                else:
                    high = x-1
            _, x, predicted = min(candidates)
            if abs(predicted-target_ns) > .05*target_ns:
                raise RuntimeError('No shutter value within5% of requested notch control')
            actual = shutter_at(x, iso)
            assert actual == predicted, 'Shutter gesture was not repeatable'
            shutter_cache[target_ns] = x
            shutter_values[target_ns] = actual
        assert abs(actual-target_ns) <= .05*target_ns
        close_exposure()
        return actual

    def refresh(hz, label):
        deadline = time.monotonic() + 8
        while True:
            text = target('dumpsys display', private=label + '-display.txt')
            mode = re.search(r'mActiveSfDisplayMode=[^\n]*?peakRefreshRate=([\d.]+)', text)
            if mode and abs(float(mode[1]) - hz) < .02:
                return float(mode[1])
            if time.monotonic() >= deadline:
                raise RuntimeError('Stock refresh did not settle: ' + str(hz))
            time.sleep(.2)

    def redraw():
        tree = ui('target')
        parents = {c: p for p in tree.iter() for c in p}
        nodes = [n for n in tree.iter('node') if n.get('text') == 'Screen timeout'
                 and n.get('package') == 'com.android.settings']
        assert len(nodes) == 1, 'Expected visible stock timeout chooser'
        row = nodes[0]
        while row.get('clickable') != 'true':
            row = parents[row]
        tap('target', row)
        assert any(n.get('text') == '10 minutes' for n in ui('target').iter('node'))
        target('input keyevent 4')
        assert any(n.get('text') == 'Screen timeout' for n in ui('target').iter('node'))
        assert target('settings get system screen_off_timeout') == '600000'

    assert target('getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; getenforce').splitlines() == ['XT2611-1', 'W3WWS36.65-64-4-1', '_b', 'Enforcing']
    assert target('id', True).startswith('uid=0(') and sh('camera', 'getprop ro.product.device') == 'PacmanPro'
    assert target('cat ' + CON + 'panelName', True) == 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
    assert target('sha256sum /vendor/lib/modules/msm_drm.ko', True).split()[0] == '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
    assert target('cat ' + CON + 'panelDC', True) == '0' and target('cat ' + CON + 'mipi_cmd_log_en', True).endswith(': 0')
    target('test ! -d ' + TRACE + f' && ! grep -q {group}/ /sys/kernel/tracing/kprobe_events', True)
    assert any(n.get('content-desc') == 'Start recording video' for n in ui('camera').iter('node'))
    metadata('before')
    keys = ('screen_brightness', 'screen_brightness_mode', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout')
    before = {k: target('settings get system ' + k) for k in keys}
    before['bl_power'] = target('cat ' + BL + 'bl_power', True)
    before['native_dbv'] = int(target('cat ' + BL + 'brightness', True))
    before['stay_on'] = target('settings get global stay_on_while_plugged_in')
    r['before'] = before
    save()
    probes = []
    instance = logger = recording = prepared = camera_changed = False
    try:
        prepared = True
        target('settings put system screen_brightness_mode 0; settings put system screen_brightness 52; settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; settings put system screen_off_timeout 600000; input keyevent 224')
        wait("dumpsys window policy | grep -F 'screenState='", 'screenState=SCREEN_STATE_ON')
        wait("dumpsys window policy | grep -F 'interactiveState='", 'interactiveState=INTERACTIVE_STATE_AWAKE')
        target('wm dismiss-keyguard')
        wait("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
        if base_rates or notch:
            target('input keyevent 3')
        target('am start -W --activity-clear-top -n ' + shlex.quote('com.android.settings/.Settings$DisplaySettingsActivity'))
        dc(0)
        target("printf '3600\n' > " + BL + 'brightness', True)
        wait('cat ' + BL + 'brightness', '3600')
        display = target('dumpsys display', private='display.txt')
        mode = re.search(r'mActiveSfDisplayMode=([^\n]+)', display)
        assert mode and 'peakRefreshRate=120.' in mode[1]
        if notch:
            redraw()
            camera_changed = True
            iso_setting(1600)
            shutter(100000, 1600)
            metadata('notch-prepared', 100000, 1600)
        target('mkdir ' + TRACE, True)
        instance = True
        for name, spec in [('param_entry', 'p:pwm_ui_ref/param_entry msm_drm:dsi_panel_send_param_cmd'),
                           ('param_return', 'r:pwm_ui_ref/param_return msm_drm:dsi_panel_send_param_cmd rc=$retval:s32'),
                           ('pcd_entry', 'p:pwm_ui_ref/pcd_entry msm_drm:dsi_panel_read_pcd_reg'),
                            ('ctrl_return', 'r:pwm_ui_ref/ctrl_return msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32')]:
            spec = spec.replace('pwm_ui_ref/', group + '/')
            target("printf '%s\n' " + shlex.quote(spec) + ' >> /sys/kernel/tracing/kprobe_events', True)
            probes.append(name)
        target('printf mono > ' + TRACE + f'/trace_clock; printf 1 > {TRACE}/events/{group}/enable; printf 1 > ' + TRACE + '/tracing_on', True)
        logger = True
        target('printf 1 > ' + CON + 'mipi_cmd_log_en', True)
        target(f"printf '<6>{marker}_BEGIN\n' > /dev/kmsg", True)
        r['media_since_epoch'] = int(time.time()) - 2
        recording = True
        camera_button('Start recording video')
        assert any(n.get('content-desc') == 'Stop recording video' for n in ui('camera').iter('node'))
        states = [(0, 120), (0, 144), (0, 120), (0, 90), (0, 120)] if base_rates else [(0, 120), (1, 120), (0, 120)]
        exposures = (100000, 500000, 700000, 1400000, 700000, 100000)
        if supported_notch:
            exposures = (100000, 500000, 1000000, 1428571, 2000000, 100000)
        if notch:
            states = [(0, 120)] * len(exposures)
        for i, (value, hz) in enumerate(states, 1):
            target(f"printf '<6>{marker}_PHASE_{i}_{value}\n' > /dev/kmsg", True)
            if base_rates:
                target(f'settings put system min_refresh_rate {hz}.0; settings put system peak_refresh_rate {hz}.0')
                refresh(hz, f'phase-{i}-start')
            dc(value)
            target("printf '3600\n' > " + BL + 'brightness', True)
            wait('cat ' + BL + 'brightness', '3600')
            actual_exposure = shutter(exposures[i-1], 1600) if notch else 100000
            if base_rates:
                redraw()
                wait('cat ' + BL + 'brightness', '3600')
            phase = {'index': i, 'dc': value, 'dbv': 3600, 'camera_start': metadata(f'phase-{i}-start', actual_exposure, 1600 if notch else 6400), 'hold_start_utc': now()}
            if notch:
                phase.update(requested_exposure_ns=exposures[i-1], exposure_ns=actual_exposure, iso=1600)
            if base_rates or notch:
                phase.update(requested_refresh=hz, redraw_completed=base_rates,
                             scene_redrawn_before_series=notch)
                target(f"printf '<6>{marker}_HOLD_{i}\n' > /dev/kmsg", True)
            r['phases'].append(phase)
            save()
            time.sleep(7)  # Bounded optical hold, not background-job polling.
            phase['hold_end_utc'] = now()
            if base_rates or notch:
                target(f"printf '<6>{marker}_END_HOLD_{i}\n' > /dev/kmsg", True)
                phase['software_refresh_end'] = refresh(hz, f'phase-{i}-end')
            phase['camera_end'] = metadata(f'phase-{i}-end', actual_exposure, 1600 if notch else 6400)
            assert target('cat ' + BL + 'brightness', True) == '3600'
            assert target('cat ' + BL + 'bl_power', True) == '0' and target('cat ' + CON + 'panelDC', True) == str(value)
            text = target('dmesg', True, f'phase-{i}-kernel.txt')
            assert 'Command transfer failed' not in text[text.index(marker + '_BEGIN'):]
            trace = target('cat ' + TRACE + '/trace', True, f'phase-{i}-trace.txt')
            assert not re.search(r'\brc=-\d+', trace) and 'LOST' not in trace
            save()
        r['six_conditions_complete' if notch else 'five_conditions_complete' if base_rates else 'three_conditions_complete'] = True
    except BaseException as error:
        r['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        errors = []
        if recording:
            try:
                if any(n.get('content-desc') == 'Stop recording video' for n in ui('camera').iter('node')):
                    camera_button('Stop recording video')
                assert any(n.get('content-desc') == 'Start recording video' for n in ui('camera').iter('node'))
                r['camera_stopped_verified'] = True
            except Exception as error:
                errors.append('Camera stop: ' + str(error))
        if camera_changed:
            try:
                iso_setting(6400)
                shutter(100000, 6400)
                r['camera_restored_metadata'] = metadata('restored')
            except Exception as error:
                errors.append('Camera settings restore: ' + str(error))
        if instance:
            try:
                target('printf 0 > ' + TRACE + '/tracing_on', True)
                target('cat ' + TRACE + '/trace', True, 'trace-final.txt')
                target('cat /sys/kernel/tracing/kprobe_profile', True, 'probe-profile.txt')
                target(f'if [ -e {TRACE}/events/{group}/enable ]; then printf 0 > {TRACE}/events/{group}/enable; fi', True)
                for name in reversed(probes):
                    target("printf '%s\n' " + shlex.quote('-:' + group + '/' + name) + ' >> /sys/kernel/tracing/kprobe_events', True)
                target('rmdir ' + TRACE, True)
            except Exception as error:
                errors.append('Trace cleanup: ' + str(error))
        if logger:
            try:
                target('printf 0 > ' + CON + 'mipi_cmd_log_en', True)
            except Exception as error:
                errors.append('Logger cleanup: ' + str(error))
        if prepared:
            try:
                dc(0)
                for k in ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode'):
                    target('settings delete system ' + k if before[k] == 'null' else 'settings put system ' + k + ' ' + shlex.quote(before[k]))
                if before['screen_brightness_mode'] == '0' and before['bl_power'] == '0':
                    target("printf '%s\n' " + str(before['native_dbv']) + ' > ' + BL + 'brightness', True)
                    wait('cat ' + BL + 'brightness', str(before['native_dbv']))
                if before['bl_power'] == '4':
                    target('input keyevent 223')
                wait('cat ' + BL + 'bl_power', before['bl_power'])
                after = {k: target('settings get system ' + k) for k in keys}
                after.update(dc=target('cat ' + CON + 'panelDC', True), logger=target('cat ' + CON + 'mipi_cmd_log_en', True), selinux=target('getenforce'),
                             native_dbv=int(target('cat ' + BL + 'brightness', True)),
                             stay_on=target('settings get global stay_on_while_plugged_in'))
                assert all(after[k] == before[k] for k in keys if k != 'screen_brightness')
                if before['screen_brightness_mode'] == '0':
                    assert after['screen_brightness'] == before['screen_brightness']
                    if before['bl_power'] == '0':
                        assert after['native_dbv'] == before['native_dbv']
                assert after['stay_on'] == before['stay_on']
                assert after['dc'] == '0' and after['logger'].endswith(': 0') and after['selinux'] == 'Enforcing'
                r.update(after=after, target_restored=True)
            except Exception as error:
                errors.append('Target restore: ' + str(error))
        if r.get('camera_stopped_verified'):
            try:
                query = sh('camera', 'content query --uri content://media/external/video/media --projection _id:_data:_size:duration:date_added --where ' + shlex.quote('date_added>=' + str(r['media_since_epoch'])))
                matches = re.findall(r'_data=(/storage/emulated/0/DCIM/OpenCamera/VID_\d+_\d+\.mp4), _size=(\d+), duration=(\d+), date_added=(\d+)', query)
                assert len(matches) == 1
                source, size, duration, _ = matches[0]
                dest = ROOT / 'artifacts/optical/current_ui_dc_reference_20261106.mp4'
                if base_rates:
                    dest = ROOT / 'artifacts/optical/pacman_stock_base_rates_20261107.mp4'
                if notch:
                    dest = ROOT / 'artifacts/optical/pacman_exposure_notch_20261107.mp4'
                if supported_notch:
                    dest = ROOT / 'artifacts/optical/pacman_exposure_notch_supported_20261107.mp4'
                assert not dest.exists()
                p = subprocess.run(['adb', '-t', str(devices['camera']), 'pull', source, str(dest)], capture_output=True, text=True, timeout=120)
                assert p.returncode == 0 and dest.stat().st_size == int(size)
                dest.chmod(0o600)
                r.update(video=str(dest.relative_to(ROOT)), video_bytes=int(size), duration_ms=int(duration))
            except Exception as error:
                errors.append('Video acquisition: ' + str(error))
        for device in devices:
            try:
                sh(device, 'rm -f ' + ui_path)
            except Exception as error:
                errors.append(device + ' UI file cleanup: ' + str(error))
        r.update(cleanup_errors=errors, finished_at_utc=now())
        save()
    print(json.dumps({k: v for k, v in r.items() if k not in ('events', 'phases')}, indent=2))
    if r.get('error') or errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
