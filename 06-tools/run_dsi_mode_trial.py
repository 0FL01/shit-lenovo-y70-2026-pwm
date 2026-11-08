#!/usr/bin/env python3
"""Fixed XT2611-1 trials and an unmodified native-ON transport control."""

import hashlib
import json
import re
import runpy
import shlex
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/dsi_mode_trial_20261106'
PRIVATE = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-mode-trial-20261106-dd-fixed')
TMP = '/data/local/tmp/pwm-mode-trial-20261106'
TRACE = '/sys/kernel/tracing/instances/pwm_mode'
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
MODULE_SHA = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
PROBES = {
    'mode_entry': 'p:pwm_mode/mode_entry msm_drm:dsi_display_cmd_transfer pending=+0x694($arg2):u32 length=$arg4:u32 flags=+3($arg3):u8',
    'mode_return': 'r:pwm_mode/mode_return msm_drm:dsi_display_cmd_transfer rc=$retval:s32',
    'mode_ctrl_return': 'r:pwm_mode/mode_ctrl_return msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32',
}

COUPLED_PROPOSAL = 'artifacts/dsi_coupled_on_20261107/proposal.md'
COUPLED_HASHES = {
    'stock': 'b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193',
    's0c1': 'dbe3e4cddda896b6c6864cbab6ff9271cff6745913afb3ccfa43a4f786c4b3b9',
}
COUPLED_9D_PROPOSAL = 'artifacts/dsi_coupled_9d_20261107/proposal.md'
COUPLED_9D_HASHES = {
    'stock': COUPLED_HASHES['stock'],
    'a0d1c1': '8604d62cb74646105413c94105a5d66273e865bda2be0e0225f5dc3f69eac62e',
}


def coupled_on_programs(out, authorization, *, keep_9d_on=False):
    """Local-only preflight; a real owner approval record is never synthesized."""
    if not __debug__:
        raise RuntimeError('Hardware trial requires Python assertions enabled')
    name = 'a0d1c1' if keep_9d_on else 's0c1'
    hashes = COUPLED_9D_HASHES if keep_9d_on else COUPLED_HASHES
    required = {
        'proposal': COUPLED_9D_PROPOSAL if keep_9d_on else COUPLED_PROPOSAL,
        'candidates': [name],
        'sequence': ['stock', name, 'stock'],
        'program_sha256': hashes,
    }
    if any(authorization.get(key) != value for key, value in required.items()):
        raise ValueError('Exact coupled proposal, sequence and image hashes must be approved')
    if authorization.get('emergency_reboot_approved') is not True:
        raise ValueError('Emergency ordinary reboot must be explicitly approved')
    if not isinstance(authorization.get('owner_confirmation'), str) or not authorization['owner_confirmation'].strip():
        raise ValueError('Missing actual owner confirmation')
    approved = datetime.fromisoformat(authorization.get('approved_at_utc', ''))
    if approved.tzinfo is None:
        raise ValueError('Approval timestamp must include timezone')
    panel = ROOT / 'artifacts/device_tree/selected_boe_v4'
    stock = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
    native_on = (panel / 'qcom,mdss-dsi-dc-on-command').read_bytes()
    candidate = (out / ('on_keep_a9_off.bin' if keep_9d_on else 'on_keep_pwm_selectors.bin')).read_bytes()
    expected = bytearray(native_on)
    if len(stock) != 875 or len(native_on) != 875:
        raise ValueError('Unexpected native table size')
    for offset in ((68,) if keep_9d_on else (68, 97)):
        if stock[offset] != 0x0e or native_on[offset] != 0x8e:
            raise ValueError('Native selector identity changed')
        expected[offset] = stock[offset]
    if candidate != expected:
        raise ValueError('Expected native ON with only A9 OFF' if keep_9d_on else 'S0C1 must equal native ON except the two OFF selectors')
    programs = {'stock': stock, name: candidate}
    if {key: hashlib.sha256(data).hexdigest() for key, data in programs.items()} != hashes:
        raise ValueError('Coupled/stock bytes differ from the proposed images')
    return programs, [('baseline', 'stock'), (name, name), ('return_' + name, 'stock')]


def wait_for_rebooted_target(serial):
    """Wait for the same handset, not whichever of two USB phones ADB selects."""
    try:
        wait = subprocess.run(['adb', '-s', serial, 'wait-for-device'],
                              capture_output=True, timeout=75)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Target reboot wait timed out') from None
    if wait.returncode:
        raise RuntimeError('Target reboot wait failed')
    devices = subprocess.run(['adb', 'devices', '-l'], capture_output=True, text=True, timeout=12)
    if devices.returncode:
        raise RuntimeError('Cannot enumerate returned target')
    ids = [int(m.group(1)) for line in devices.stdout.splitlines()
           if len(line.split()) > 2 and line.split()[0] == serial and line.split()[1] == 'device'
           and 'device:avr' in line.split()
           and (m := re.search(r'\btransport_id:(\d+)', line))]
    if len(ids) != 1:
        raise RuntimeError('Cannot independently select returned target')
    return ids[0]


def new_camera_video(before, after):
    """Select exactly this recording, independent of the camera's wall clock."""
    def files(text):
        paths = text.splitlines()
        if len(paths) != len(set(paths)) or any(
                not re.fullmatch(r'/sdcard/DCIM/OpenCamera/[A-Za-z0-9_.-]+\.mp4', path)
                for path in paths):
            raise ValueError('Unexpected Open Camera video listing')
        return set(paths)

    prior, current = files(before), files(after)
    added = current - prior
    if not prior <= current or len(added) != 1:
        raise ValueError('Expected exactly one new Open Camera video')
    return added.pop()


def main():
    global TMP
    reproduction = len(sys.argv) > 1 and sys.argv[1] == '--a9-reproduce'
    guarded = None
    trial_dbv = 3600
    if reproduction:
        from a9_reproduction import prepare, lock_commands, validate_c1_trace
        config, fresh_out, fresh_private, fresh_programs, fresh_scope = prepare(ROOT, sys.argv[2:])
        if config.offline_check:
            print(json.dumps(fresh_scope, indent=2))
            return
        from guarded_adb_socket import GuardedADB
        guarded = GuardedADB()
        guarded.preflight()
        guarded.bind(config.target)
        guarded.bind(config.camera)
        # Reserve both names before any device command; never reuse a partial run.
        fresh_private.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fresh_private.mkdir(mode=0o700)
        fresh_out.mkdir()
        (fresh_out / 'authorization_scope.json').write_text(json.dumps(fresh_scope, indent=2) + '\n')
        lock_token = config.experiment_id + '_' + uuid.uuid4().hex[:12]
        lock_ops = lock_commands(lock_token)
        lock_record = fresh_private / 'lock-owner.txt'
        lock_record.write_text(lock_token + '\n')
        lock_record.chmod(0o600)
        trial_dbv = config.dbv
        TMP = '/data/local/tmp/' + config.experiment_id
        sys.argv = [sys.argv[0], str(config.target), str(config.camera), '--coupled-9d']
    adb_run = guarded.run if guarded else subprocess.run
    assert len(sys.argv) in (3, 4), 'Usage: run_dsi_mode_trial.py TARGET_TRANSPORT CAMERA_TRANSPORT [--blocks|--blocks-redraw|--selector-split|--coupled-on|--coupled-9d|--coupled-on-view|--coupled-on-return|--coupled-9d-view|--coupled-9d-return|--stock-on|--stock-on-dbv|--stock-on-redraw]'
    option = sys.argv[3] if len(sys.argv) == 4 else ''
    assert option in ('', '--blocks', '--blocks-redraw', '--selector-split', '--coupled-on', '--coupled-9d', '--coupled-on-view', '--coupled-on-return', '--coupled-9d-view', '--coupled-9d-return', '--stock-on', '--stock-on-dbv', '--stock-on-redraw')
    owner_view = option in ('--coupled-on-view', '--coupled-9d-view')
    owner_return = option in ('--coupled-on-return', '--coupled-9d-return')
    manual_session = owner_view or owner_return
    coupled_9d = option in ('--coupled-9d', '--coupled-9d-view', '--coupled-9d-return')
    coupled_on = option == '--coupled-on' or manual_session or coupled_9d
    if coupled_on and not __debug__:
        raise RuntimeError('Hardware trial requires Python assertions enabled')
    selector_split = option == '--selector-split'
    short_read_control = selector_split or coupled_on
    blocks_redraw = option in ('--blocks-redraw', '--selector-split') or coupled_on
    blocks = option in ('--blocks', '--blocks-redraw', '--selector-split')
    stock_control = option in ('--stock-on', '--stock-on-dbv', '--stock-on-redraw')
    redraw_control = option == '--stock-on-redraw'
    replay_dbv = blocks_redraw or option in ('--stock-on-dbv', '--stock-on-redraw')
    transports = {'target': int(sys.argv[1]), 'camera': int(sys.argv[2])}
    assert transports['target'] != transports['camera']
    out = ROOT / 'artifacts/dsi_block_trials_20261106' if blocks else OUT
    private_dir = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-block-trials-20261106') if blocks else PRIVATE
    if blocks_redraw:
        out = out / 'with_redraw'
        private_dir = Path(str(private_dir) + '-redraw')
    if selector_split:
        out = ROOT / 'artifacts/dsi_selector_split_20261107'
        private_dir = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-selector-split-20261107')
    if coupled_on:
        out = ROOT / ('artifacts/dsi_coupled_9d_20261107' if coupled_9d else 'artifacts/dsi_coupled_on_20261107')
        private_dir = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-coupled-9d-20261107' if coupled_9d else '/home/stfu/.cache/opencode-tmp/opencode/dsi-coupled-on-20261107')
        if manual_session:
            out = out / 'owner_view'
            private_dir = Path(str(private_dir) + '-owner-view')
            if owner_return:
                out = out / 'return'
                private_dir = Path(str(private_dir) + '-return')
    if stock_control:
        out = ROOT / 'artifacts/dsi_stock_on_control_20261106'
        private_dir = Path('/home/stfu/.cache/opencode-tmp/opencode/dsi-stock-on-control-20261106')
        if redraw_control:
            out = out / 'with_redraw'
            private_dir = Path(str(private_dir) + '-redraw')
        elif replay_dbv:
            out = out / 'with_dbv_replay'
            private_dir = Path(str(private_dir) + '-dbv')
    if reproduction:
        out, private_dir = fresh_out, fresh_private
        authorization = fresh_scope  # Public scope only; owner quote remains in private source.
        blocks_redraw = True
    else:
        authorization = json.loads(((out.parent if owner_return else out) / 'authorization.json').read_text())
    view_report = None
    if manual_session:
        assert authorization.get('owner_view_approved') is True
        if owner_return:
            view_report = json.loads((out.parent / 'run.json').read_text())
            assert view_report.get('owner_view_active') is True
            assert view_report.get('pending_bytes_may_exist') is False, 'Uncertain queue requires recovery, not appending stock'
            saved_dbv = view_report['before']['native_dbv']
            assert type(saved_dbv) is int and 0 <= saved_dbv <= 16180, 'Invalid saved native DBV'
    report_path = out / 'run.json'
    assert not report_path.exists(), 'One-shot experiment; do not repeat'
    parse = runpy.run_path(str(ROOT / '06-tools/inspect_cn_dtbo.py'))['packets']
    ranges = [[0, 253], [253, 500], [500, 754], [754, 864], [864, 875]]
    if reproduction:
        programs = fresh_programs
        stages = [('baseline', 'stock'), ('a9_only', 'a9_only'), ('return_a9_only', 'stock')]
    elif coupled_on:
        source = ROOT / 'artifacts/dsi_coupled_9d_20261107' if coupled_9d else ROOT / 'artifacts/dsi_coupled_on_20261107'
        programs, stages = coupled_on_programs(source, authorization, keep_9d_on=coupled_9d)
        if owner_view:
            stages = stages[:2]  # Return is a separately invoked part of this manual session.
        elif owner_return:
            stages = stages[-1:]
    elif blocks:
        assert authorization['candidates'] == (['a9_only', '9d_only'] if selector_split else (['mode90'] if blocks_redraw else []) + ['thresholds', 'page53', 'page63'])
        panel = ROOT / 'artifacts/device_tree/selected_boe_v4'
        stock = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
        native_on = parse((panel / 'qcom,mdss-dsi-dc-on-command').read_bytes())
        native_off = parse(stock)
        programs = {'stock': stock}
        specifications = {
            'thresholds': [(6, 0x23, 0xa9), (9, 0x24, 0x9d)],
            'page53': [(16, 0x53, 0x95), (17, 0x53, 0xa2)],
            'page63': [(27, 0x63, 0xf2), (28, 0x63, 0xf3)],
        }
        if selector_split:
            specifications = {'a9_only': [(6, 0x23, 0xa9)], '9d_only': [(9, 0x24, 0x9d)]}
        elif blocks_redraw:
            specifications = {'mode90': [(12, 0x23, 0x80)], **specifications}
        stages = [('baseline', 'stock')]
        for name, fields in specifications.items():
            expected = bytearray(stock)
            for index, page, opcode in fields:
                before_packet, after_packet = native_off[index], native_on[index]
                assert before_packet['header_hex'] == after_packet['header_hex']
                assert before_packet['page'] == after_packet['page'] == page
                payload = bytes.fromhex(after_packet['payload_hex'])
                assert payload[0] == bytes.fromhex(before_packet['payload_hex'])[0] == opcode
                start = before_packet['offset_in_property'] + 7
                expected[start:start + len(payload)] = payload
            candidate_path = OUT / 'dc_off_mode90.bin' if name == 'mode90' else ROOT / 'artifacts/dsi_block_trials_20261106' / (name + '.bin')
            if selector_split:
                candidate_path = out / (name + '.bin')
            program = candidate_path.read_bytes()
            assert program == expected and program[126] == (0x90 if name == 'mode90' else 0x50)
            programs[name] = program
            stages.extend([(name, name), ('return_' + name, 'stock')])
    elif stock_control:
        panel = ROOT / 'artifacts/device_tree/selected_boe_v4'
        stock = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
        native_on = (panel / 'qcom,mdss-dsi-dc-on-command').read_bytes()
        programs = {'stock': stock, 'native_on': native_on}
        stages = [('baseline', 'stock'), ('native_on', 'native_on'), ('return', 'stock')]
    else:
        validation = json.loads((out / 'validation.json').read_text())
        stock = (ROOT / validation['stock_source']).read_bytes()
        candidate = (ROOT / validation['candidate']).read_bytes()
        assert len(stock) == len(candidate) == 875
        assert [i for i, (a, b) in enumerate(zip(stock, candidate)) if a != b] == [126]
        assert stock[126] == 0x50 and candidate[126] == 0x90
        assert ranges == validation['native_debugfs_write_byte_ranges_end_exclusive']
        programs = {'stock': stock, 'candidate': candidate}
        stages = [('baseline', 'stock'), ('candidate', 'candidate'), ('return', 'stock')]
    for program in programs.values():
        assert len(program) == 875
        packets = parse(program)
        assert len(packets) == 75
        assert [bytes.fromhex(p['header_hex'])[3] for p in packets] == [64] * 74 + [0]
        for start, end in ranges:
            assert parse(program[start:end]) and end - start < 256
    if owner_return:
        out.mkdir()
    if not reproduction:
        private_dir.mkdir(mode=0o700)
    chunks_dir = private_dir / 'chunks'
    chunks_dir.mkdir(mode=0o700)
    for name, program in programs.items():
        for i, (start, end) in enumerate(ranges):
            path = chunks_dir / f'{name}_{i}.txt'
            path.write_text(' '.join(f'0x{x:02x}' for x in program[start:end]))
            path.chmod(0o600)
    report = {'started_at_utc': now(), 'authorization': authorization,
              'candidate_attempts': 0,
              'candidate_attempts_by_name': {name: 0 for name in programs if name != 'stock'},
              'stages': [], 'events': [], 'pwm_hz': 'unknown'}
    if reproduction:
        report.update(mode='a9_reproduction', experiment_id=config.experiment_id,
                      trial_native_dbv=trial_dbv, transport='existing_private_unix_socket_only',
                      adb_protocol=41, live_transport_validation='coordinator-qualified read-only separately')
    created_probes = []
    instance_created = tmp_created = settings_changed = logger_on = recording = False
    pending_uncertain = candidate_active = False
    reader_started = False
    lock_acquired = False
    entry_count = 0
    before = {}
    camera_files_before = ''
    marker = 'PWM_BLOCK' if blocks else 'PWM_MODE'
    if blocks_redraw:
        marker = 'PWM_BLOCK_REDRAW'
    if selector_split:
        marker = 'PWM_SELECTOR_SPLIT'
    if coupled_on:
        marker = 'PWM_COUPLED_ON'
        if coupled_9d:
            marker = 'PWM_COUPLED_9D'
        if manual_session:
            marker = 'PWM_COUPLED_ON_VIEW_RETURN' if owner_return else 'PWM_COUPLED_ON_VIEW'
    if stock_control:
        marker = 'PWM_STOCK_ON_DBV' if replay_dbv else 'PWM_STOCK_ON'
    if redraw_control:
        marker = 'PWM_STOCK_ON_REDRAW'

    if reproduction:
        from dsi_trial_transaction import experiment_marker
        marker = experiment_marker(config.experiment_id)
        report['kernel_marker_prefix'] = marker

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def shell(device, command, *, root=False, private=None, timeout=25):
        remote = 'su -c ' + shlex.quote(command) if root else command
        p = adb_run(['adb', '-t', str(transports[device]), 'shell', remote],
                           capture_output=True, text=True, timeout=timeout)
        if reproduction and private is None:
            private = 'event-' + str(len(report['events'])) + '.txt'
        if private:
            path = private_dir / private
            path.write_text(p.stdout)
            path.chmod(0o600)
        report['events'].append({'at_utc': now(), 'device': device, 'command': remote.replace(lock_token, '<private lock token>') if reproduction else remote,
                                 'exit_code': p.returncode,
                                 'stdout': '<private ' + private + '>' if private else p.stdout.strip(),
                                 'stderr': '<redacted>' if reproduction else p.stderr.strip()})
        save()
        if p.returncode:
            raise RuntimeError('Command failed: ' + command)
        return p.stdout.strip()

    def target(command, **kwargs):
        return shell('target', command, **kwargs)

    def wait_target(command, expected, seconds=6):
        deadline = time.monotonic() + seconds
        while target(command, root=True) != expected:
            if time.monotonic() >= deadline:
                raise RuntimeError('State timeout: ' + command)
            time.sleep(.15)

    def enable_logger():
        nonlocal logger_on
        assert not logger_on, 'Logger already enabled'
        logger_on = True  # Cleanup must disable it even if the write outcome is uncertain.
        target("printf '1\\n' > " + CON + 'mipi_cmd_log_en', root=True)

    def camera_ui():
        text = shell('camera', 'uiautomator dump /data/local/tmp/pwm-mode-camera.xml >/dev/null && cat /data/local/tmp/pwm-mode-camera.xml', private='camera-ui.xml')
        return ET.fromstring(text)

    def camera_tap(description):
        nodes = [n for n in camera_ui().iter('node') if n.get('content-desc') == description]
        assert len(nodes) == 1, description
        a, b, c, d = map(int, re.findall(r'\d+', nodes[0].get('bounds')))
        shell('camera', f'input tap {(a+c)//2} {(b+d)//2}')

    native_reference = None
    last_capture = None
    def camera_metadata(label):
        nonlocal last_capture
        if reproduction:
            from camera_capture_metadata import validate_capture
            text = shell('camera', 'dumpsys media.camera', private=label + '-camera.txt')
            captured = validate_capture(text, previous=last_capture if recording else None,
                                        expected_size=(1280, 720) if recording else None,
                                        require_recording=recording)
            if recording:
                last_capture = captured
            return captured
        keys = ('android.sensor.exposureTime', 'android.sensor.sensitivity',
                 'android.control.aeMode', 'android.control.afMode', 'android.lens.focusDistance',
                 'android.sensor.rollingShutterSkew', 'android.sensor.timestamp',
                 'android.request.frameCount', 'android.scaler.cropRegion',
                 'android.control.zoomRatio', 'android.control.videoStabilizationMode',
                 'android.lens.opticalStabilizationMode')
        required = (keys[0], keys[1], keys[2], keys[3], keys[4], keys[8], keys[9], keys[10], keys[11])
        for sample in range(3 if coupled_9d else 1):
            suffix = '' if sample == 0 else '-retry-' + str(sample)
            text = shell('camera', 'dumpsys media.camera', private=label + '-camera' + suffix + '.txt')
            data = {k: [v.strip() for v in re.findall(re.escape(k) + r'[^\n]*\n\s*\[([^\]]+)\]', text)[:2]] for k in keys}
            if not coupled_9d or all(len(data[k]) == 2 for k in required):
                break
            time.sleep(.2)
        assert data['android.sensor.exposureTime'] == ['100000'] * 2
        assert data['android.sensor.sensitivity'] == ['6400'] * 2
        assert data['android.control.aeMode'] == data['android.control.afMode'] == ['OFF'] * 2
        assert len(data['android.lens.focusDistance']) == 2
        expected_focus = 2.03874850 if coupled_9d else 9.11752701
        assert all(abs(float(x) - expected_focus) < .001 for x in data['android.lens.focusDistance'])
        assert data['android.control.videoStabilizationMode'] == ['OFF'] * 2
        assert data['android.lens.opticalStabilizationMode'] == ['OFF'] * 2
        if coupled_9d:
            assert data['android.scaler.cropRegion'] == ['0 0 4080 3072'] * 2
        if coupled_on:
            geometry = ('android.scaler.cropRegion', 'android.control.zoomRatio')
            for key in geometry:
                assert len(data[key]) == 2 and data[key][0] == data[key][1], key
            # Compare recording to recording, not to the potentially different preview crop.
            reference = report['stages'][0].get('camera_start') if report['stages'] else None
            if reference:
                assert all(data[key] == reference[key] for key in geometry), 'Camera geometry changed'
        return data

    def identity():
        assert target('getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce').splitlines() == [
            'XT2611-1', 'W3WWS36.65-64-4-1', '_b',
            '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k', 'Enforcing']
        assert target('id', root=True).startswith('uid=0(')
        if reproduction:
            assert target('getprop ro.product.device') == 'avr'
        assert target('cat ' + CON + 'panelName', root=True) == 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'
        assert target('sha256sum /vendor/lib/modules/msm_drm.ko', root=True).split()[0] == MODULE_SHA

    def state():
        assert target('cat ' + BL + 'brightness', root=True) == str(trial_dbv)
        assert target('cat ' + BL + 'bl_power', root=True) == '0'
        assert target('cat ' + CON + 'panelDC', root=True) == '0'
        assert target('getenforce') == 'Enforcing'

    def create_stock_anchor():
        from dsi_trial_transaction import stock_anchor_settings, validate_stock_anchor
        if report.get('stock_native_anchor_attempted') or pending_uncertain or candidate_active or report['candidate_attempts']:
            raise RuntimeError('Stock anchor is one-shot and must precede any table/candidate')
        report['stock_native_anchor_attempted'] = True
        report['stock_native_anchor'] = []
        save()
        for hz in (90, 120):
            begin = marker + '_STOCK_ANCHOR_BEGIN_' + str(hz)
            end = marker + '_STOCK_ANCHOR_END_' + str(hz)
            target("printf '<6>" + begin + "\\n' > /dev/kmsg", root=True)
            target(stock_anchor_settings(hz))  # Exactly one settings request per step; polls are read-only.
            deadline = time.monotonic() + 15
            sample = 0
            while True:
                display = target('dumpsys display', private=f'anchor-{hz}-display-{sample}.txt')
                match = re.search(r'mActiveSfDisplayMode=[^\n]*peakRefreshRate=([0-9.]+)', display)
                log = target('dmesg', root=True, private=f'anchor-{hz}-kernel-{sample}.txt')
                if match and abs(float(match[1])-hz) < .03:
                    try:
                        validate_stock_anchor(log, begin, hz)
                        break
                    except ValueError:
                        pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Fresh software/native stock anchor not observed; no retry')
                sample += 1
                time.sleep(.2)
            state()
            target("printf '<6>" + end + "\\n' > /dev/kmsg", root=True)
            log = target('dmesg', root=True, private=f'anchor-{hz}-qualified-kernel.txt')
            evidence = validate_stock_anchor(log, begin, hz, end)
            evidence['software_observed_hz'] = float(match[1])
            report['stock_native_anchor'].append(evidence)
            save()
        report['stock_native_anchor_complete'] = True
        save()

    def qualify_native(label):
        nonlocal native_reference
        from dsi_trial_transaction import qualify_quiet
        deadline = time.monotonic() + 30
        attempt = 0
        while True:
            begin = marker + '_QUIET_BEGIN_' + label + '_' + str(attempt)
            end = marker + '_QUIET_END_' + label + '_' + str(attempt)
            target("printf '<6>" + begin + "\\n' > /dev/kmsg", root=True)
            time.sleep(2)
            target("printf '<6>" + end + "\\n' > /dev/kmsg", root=True)
            log = target('dmesg', root=True, private=label + '-quiet-' + str(attempt) + '.txt')
            try:
                current = qualify_quiet(log, begin, end, native_reference)
            except ValueError:
                # Only initial stock setup may settle. No retries with a candidate active.
                if native_reference is not None or time.monotonic() >= deadline:
                    raise
                attempt += 1
                continue
            native_reference = current
            report['native_mode_reference'] = current
            save()
            return {'native_state': current, 'quiet_seconds': 2, 'attempts': attempt + 1,
                    'end_marker': end, 'race_limit': 'not an atomic compositor lock'}

    def trace_check(expected_pending, expected_length, expected_flags):
        nonlocal entry_count
        text = target('cat ' + TRACE + '/trace', root=True, private='trace-latest.txt')
        assert 'LOST' not in text and not re.search(r'\brc=-\d+', text), 'Native trace error'
        entries = re.findall(r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)', text)
        returns = re.findall(r'\bmode_return:.*?rc=(-?\d+)', text)
        assert len(entries) == len(returns) == entry_count + 1, 'Incomplete or unexpected callback trace'
        assert tuple(map(int, entries[-1])) == (expected_pending, expected_length, expected_flags), entries[-1]
        assert int(returns[-1]) == 0, returns[-1]
        entry_count += 1

    def esd_mode():
        command = (f'set -e; mount -o rprivate none /; '
                   f'mount -t debugfs -o ro,nosuid,nodev,noexec debugfs {TMP}/debugfs; '
                   f"tr -d '\\000' < {TMP}/debugfs/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode; "
                   f'umount {TMP}/debugfs')
        return target('timeout -k 3 15 unshare -m /system/bin/sh -c ' + shlex.quote(command), root=True)

    def selector_readback(label, name):
        nonlocal entry_count, reader_started
        from check_ddic_stock_latch import reader
        reader_started = True
        target("printf '<6>" + marker + '_READ_BEGIN_' + label + "\\n' > /dev/kmsg", root=True)
        raw = target(reader(mount_dir=TMP + '/debugfs', reads=((0x23, 0xa9, 1), (0x24, 0x9d, 1), (0, 0x52, 2))),
                     root=True, private=label + '-readback.txt')
        assert 'ESD_ISOLATED esd_sw_sim_success' in raw, 'ESD isolation was not verified before register reads'
        assert 'ESD_RESTORED reg_read' in raw
        values = {}
        for line in raw.splitlines():
            match = re.fullmatch(r'R ([0-9A-F]{2}:[0-9A-F]{2}) (.+)', line.strip())
            if match:
                assert match[1] not in values
                values[match[1]] = list(bytes.fromhex(match[2].replace('0x', '')))
        expected = {'23:A9': [0x8e if name == 'a9_only' else 0x0e],
                     '24:9D': [0x8e if name in ('9d_only', 'a0d1c1') else 0x0e], '00:52': list(trial_dbv.to_bytes(2, 'big'))}
        assert values == expected, (values, expected)
        text = target('cat ' + TRACE + '/trace', root=True, private=label + '-readback-trace.txt')
        entries = re.findall(r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)', text)
        returns = re.findall(r'\bmode_return:.*?rc=(-?\d+)', text)
        # Three page/read/page0 operations plus EXIT page0; all standalone11-byte packets.
        assert len(entries) == len(returns) == entry_count + 7
        assert all(tuple(map(int, v)) == (0, 11, 0) for v in entries[-7:])
        assert all(int(v) == 0 for v in returns[-7:]) and 'LOST' not in text and not re.search(r'\brc=-\d+', text)
        entry_count += 7
        target("printf '<6>" + marker + '_READ_END_' + label + "\\n' > /dev/kmsg", root=True)
        return {'values': values, 'esd': 'reg_read', 'esd_isolation_verified': True,
                'page_callbacks_verified': 7, 'at_utc': now()}

    def capture_c1_stage(label):
        nonlocal entry_count
        from capture_ddic_c1 import reader_script, validate_capture
        state()
        target(lock_ops['verify'], root=True)
        nonce = uuid.uuid4().hex[:12]
        trace_before = target('cat ' + TRACE + '/trace', root=True, private=label + '-c1-trace-before.txt')
        raw = target(reader_script(nonce, trial_dbv, 120, held_token=lock_token),
                     root=True, private=label + '-c1-capture.txt', timeout=40)
        data = validate_capture(raw, nonce, trial_dbv, 120)
        trace_after = target('cat ' + TRACE + '/trace', root=True, private=label + '-c1-trace-after.txt')
        delta = validate_c1_trace(trace_before, trace_after, entry_count)
        entry_count = delta['entry_count_after']
        target(lock_ops['verify'], root=True)  # Child must leave parent's ownership intact.
        assert esd_mode() == 'reg_read'
        state()
        return {**data, 'main_trace': delta, 'at_utc': now(),
                'interpretation': 'A9-status comparison only; no frequency inference'}

    def repaint_settings(label):
        """Open/cancel the stock timeout chooser; do not change any preference."""
        def ui(suffix):
            return ET.fromstring(target(f'uiautomator dump {TMP}/redraw-ui.xml >/dev/null && cat {TMP}/redraw-ui.xml',
                                        private=label + '-' + suffix + '-ui.xml'))

        for _ in range(3):
            tree = ui('before')
            parents = {c: p for p in tree.iter() for c in p}
            labels = [n for n in tree.iter('node') if n.get('text') == 'Screen timeout' and n.get('package') == 'com.android.settings']
            if len(labels) == 1:
                row = labels[0]
                while row.get('clickable') != 'true':
                    row = parents[row]
                assert not any(n.get('checkable') == 'true' for n in row.iter('node'))
                a, b, c, d = map(int, re.findall(r'\d+', row.get('bounds')))
                target(f'input tap {(a+c)//2} {(b+d)//2}')
                opened = ui('opened')
                # The actual temporary timeout is10min. Opening/cancelling must not select a value.
                assert any(n.get('text') == '10 minutes' for n in opened.iter('node'))
                target('input keyevent 4')
                returned = ui('returned')
                assert any(n.get('text') == 'Screen timeout' for n in returned.iter('node'))
                assert target('settings get system screen_off_timeout') == '600000'
                state()
                return
            target('input swipe 720 2780 720 850 400')
        raise RuntimeError('Native timeout chooser unavailable; no blind redraw action')

    def observe_stage(stage, label):
        state()
        if not manual_session:
            stage['camera_start'] = camera_metadata(label + '-start')
        if reproduction:
            stage['kernel_markers'] = {'hold_begin': marker + '_HOLD_BEGIN_' + label,
                                       'hold_end': marker + '_HOLD_END_' + label}
            target("printf '<6>" + stage['kernel_markers']['hold_begin'] + "\\n' > /dev/kmsg", root=True)
        stage['hold_start_utc'] = now()
        save()
        print(json.dumps({'stage': label, 'packets': stage.get('native_packets_matched', 0), 'hold_start_utc': stage['hold_start_utc']}), flush=True)
        time.sleep(1 if manual_session else 7)  # Bounded completion check; manual inspection follows cleanup.
        stage['hold_end_utc'] = now()
        if reproduction:
            target("printf '<6>" + stage['kernel_markers']['hold_end'] + "\\n' > /dev/kmsg", root=True)
        state()
        if not manual_session:
            stage['camera_end'] = camera_metadata(label + '-end')
        text = target('dmesg', root=True, private=label + '-kernel.txt')
        assert 'Command transfer failed' not in text[text.index(marker + '_BEGIN_' + label):], 'Native DMA failure during hold'
        if reproduction:
            from dsi_trial_transaction import marker_interval
            hold = marker_interval(text, stage['kernel_markers']['hold_begin'], stage['kernel_markers']['hold_end'])
            assert 'dsi_ctrl_cmd_transfer len=' not in hold and 'dsi_display_set_mode' not in hold, 'Unexpected native DSI/mode change during optical hold'
            from dsi_trial_transaction import native_state
            assert native_state(text) == native_reference, 'Native mode differs from baseline during optical hold'
            stage['native_state_after_hold'] = native_reference
            stage['hold_no_native_dsi_writes_verified'] = True
        stage['completion_error_log_checked_through_utc'] = now()
        return text

    def observe_redraw():
        label = 'native_on_redraw'
        stage = {'label': label, 'started_at_utc': now(), 'new_table_sent': False}
        report['stages'].append(stage)
        target("printf '<6>" + marker + '_BEGIN_' + label + "\\n' > /dev/kmsg", root=True)
        repaint_settings(label)
        text = observe_stage(stage, label)
        section = text[text.index(marker + '_BEGIN_' + label):]
        writes = re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)', section)
        stage['writes_during_redraw_and_hold'] = [{'length': int(n), 'type': int(k, 16), 'mode': mode, 'payload': data.strip()} for n, k, mode, data in writes]
        assert not writes, 'Redraw also issued DSI writes; not a frame-only comparison'
        text = target('cat ' + TRACE + '/trace', root=True, private='redraw-trace.txt')
        assert 'LOST' not in text and not re.search(r'\brc=-\d+', text)
        target("printf '<6>" + marker + '_END_' + label + "\\n' > /dev/kmsg", root=True)
        save()

    def apply_program(label, name, program):
        nonlocal pending_uncertain, candidate_active, entry_count
        state()
        qualification = qualify_native(label) if reproduction else None
        stage = {'label': label, 'started_at_utc': now(), 'chunks_verified': 0}
        if reproduction:
            stage['native_qualification'] = qualification
        report['stages'].append(stage)
        if name != 'stock':
            assert report['candidate_attempts_by_name'][name] == 0
            report['candidate_attempts_by_name'][name] = 1
            report['candidate_attempts'] += 1
            candidate_active = True
            report['candidate_may_be_active'] = True
        save()
        target("printf '<6>" + marker + '_BEGIN_' + label + "\\n' > /dev/kmsg", root=True)
        if reproduction:
            from dsi_trial_transaction import transaction_script, validate_batch_capture
            pending_uncertain = True
            report['pending_bytes_may_exist'] = True
            save()
            raw = target(transaction_script(TMP, TRACE, name, entry_count), root=True,
                         private=label + '-transaction.txt', timeout=30)
            verified = validate_batch_capture(raw, entry_count)
            entry_count = verified['entry_count_after']
            stage['transaction'] = verified
            stage['chunks_verified'] = verified['chunks_verified']
            save()
        else:
            for i, (start, end) in enumerate(ranges):
                pending_uncertain = True
                report['pending_bytes_may_exist'] = True
                save()
                # Regular input file + a single dd block: no shell stdio splitting of the TX write.
                command = (f'set -e; mount -o rprivate none /; '
                           f'mount -t debugfs -o nosuid,nodev,noexec debugfs {TMP}/debugfs; '
                           f'test -f {TMP}/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd; '
                           f'test -w {TMP}/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd; '
                           f'dd if={TMP}/chunks/{name}_{i}.txt '
                           f'of={TMP}/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd '
                           'bs=4096 count=1 conv=notrunc status=none')
                target('unshare -m /system/bin/sh -c ' + shlex.quote(command), root=True)
                trace_check(start, end - start, 64 if i < 4 else 0)
                stage['chunks_verified'] += 1
                save()
        target("printf '<6>" + marker + '_END_' + label + "\\n' > /dev/kmsg", root=True)
        text = target('dmesg', root=True, private=label + '-kernel.txt')
        start = text.index(marker + '_BEGIN_' + label)
        section = text[start:text.index(marker + '_END_' + label, start)]
        assert 'Command transfer failed' not in section, 'Native DMA completion failure'
        if reproduction:
            from dsi_trial_transaction import native_state
            assert native_state(text) == native_reference, 'Native mode changed during transaction'
            assert 'dsi_display_set_mode' not in text.split(qualification['end_marker'], 1)[1], 'Native mode transition after qualification'
        wire = re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)', section)
        observed = [(int(n), int(kind, 16), mode, bytes.fromhex(data)) for n, kind, mode, data in wire]
        expected = [(len(bytes.fromhex(p['payload_hex'])), bytes.fromhex(p['header_hex'])[0],
                     'hs', bytes.fromhex(p['payload_hex'])) for p in parse(program)]
        assert observed == expected, 'Native packets differ from the exact approved program'
        stage.update(native_packets_matched=75, transmission_verified_at_utc=now())
        if replay_dbv:
            target("printf '<6>" + marker + '_DBV_BEGIN_' + label + "\\n' > /dev/kmsg", root=True)
            target("printf '%s\\n' " + str(trial_dbv) + " > " + BL + 'brightness', root=True)
            wait_target('cat ' + BL + 'brightness', str(trial_dbv))
            target("printf '<6>" + marker + '_DBV_END_' + label + "\\n' > /dev/kmsg", root=True)
            text = target('dmesg', root=True, private=label + '-dbv-kernel.txt')
            begin = text.index(marker + '_DBV_BEGIN_' + label)
            section = text[begin:text.index(marker + '_DBV_END_' + label, begin)]
            writes = re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)', section)
            decoded = [(int(n), int(k, 16), mode, bytes.fromhex(data)) for n, k, mode, data in writes]
            assert decoded.count((3, 0x39, 'hs', bytes([0x51]) + trial_dbv.to_bytes(2, 'big'))) == 1
            assert 'Command transfer failed' not in section
            stage['same_dbv_replay'] = {'at_utc': now(), 'dbv': trial_dbv,
                                        'observed_writes': [{'length': n, 'type': k, 'mode': mode, 'payload': data.hex(' ')} for n, k, mode, data in decoded]}
        if blocks_redraw or (redraw_control and name == 'stock'):
            if reproduction:
                target("printf '<6>" + marker + '_REDRAW_BEGIN_' + label + "\\n' > /dev/kmsg", root=True)
            repaint_settings(label)
            if reproduction:
                target("printf '<6>" + marker + '_REDRAW_END_' + label + "\\n' > /dev/kmsg", root=True)
                from a9_reproduction import verify_redraw_interval
                redraw_log = target('dmesg', root=True, private=label + '-redraw-kernel.txt')
                stage['redraw_audit'] = verify_redraw_interval(redraw_log, marker, label)
                save()
            stage['redraw_completed'] = True
            if name == 'stock':
                stage['stock_redraw_completed'] = True
        if short_read_control:
            stage['readback'] = selector_readback(label, name)
        if reproduction and config.capture_c1:
            stage['c1_capture'] = capture_c1_stage(label)
            save()
        observe_stage(stage, label)
        if reproduction:
            stage['readback_after_hold'] = selector_readback(label + '_after_hold', name)
        pending_uncertain = False
        report['pending_bytes_may_exist'] = False
        if name == 'stock':
            candidate_active = False
            report['candidate_may_be_active'] = False
        save()

    def recover_reboot():
        nonlocal pending_uncertain, candidate_active, instance_created, logger_on
        report['recovery_reboot_requested_at_utc'] = now()
        save()
        p = adb_run(['adb', '-t', str(transports['target']), 'reboot'],
                           capture_output=True, text=True, timeout=15)
        assert p.returncode == 0, 'Recovery reboot not accepted'
        if guarded:
            guarded.wait_target(target_serial)  # Keep immutable role aliases bound to serials.
        else:
            transports['target'] = wait_for_rebooted_target(target_serial)
        wait_target('getprop sys.boot_completed', '1', seconds=60)
        identity()
        assert target('cat ' + CON + 'panelDC', root=True) == '0'
        pending_uncertain = candidate_active = instance_created = logger_on = False
        created_probes.clear()
        report['recovery_reboot_verified'] = True
        if reproduction and report.get('watchdog_armed'):
            target(f'rmdir {TMP}/watchdog_armed', root=True)
            report['watchdog_disarmed_after_recovery'] = True
        report['pending_bytes_may_exist'] = report['candidate_may_be_active'] = False
        save()

    keys = ('screen_brightness', 'screen_brightness_mode', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout')
    try:
        identity()
        if reproduction:
            from dsi_trial_transaction import ensure_unused_marker
            prior_kernel = target('dmesg', root=True, private='preflight-marker-collision-kernel.txt')
            ensure_unused_marker(prior_kernel, config.experiment_id)
            target(lock_ops['acquire'], root=True)
            lock_acquired = True
            report['exclusive_device_lock_acquired'] = True
        serial_check = adb_run(['adb', '-t', str(transports['target']), 'get-serialno'],
                                      capture_output=True, text=True, timeout=10)
        assert serial_check.returncode == 0 and serial_check.stdout.strip() not in ('', 'unknown'), 'Target serial unavailable for recovery'
        target_serial = serial_check.stdout.strip()  # In memory only; never log the serial.
        if owner_return:
            candidate_active = True
            report['candidate_may_be_active'] = True
        if not manual_session:
            if coupled_9d:
                assert shell('camera', 'getprop ro.product.device; getprop ro.boot.hardware.sku').splitlines() == ['Galaga', 'ROW']
            else:
                assert shell('camera', 'getprop ro.product.device') == 'PacmanPro'
            if reproduction:
                assert shell('camera', 'getprop ro.product.model') == 'A001'
                package = shell('camera', 'dumpsys package net.sourceforge.opencamera', private='camera-package.txt')
                assert re.search(r'\bversionName=1\.56\.2(?:\s|$)', package)
            camera_metadata('preflight')
            ui_nodes = list(camera_ui().iter('node'))
            assert any(n.get('content-desc') == 'Start recording video' for n in ui_nodes)
            if coupled_9d:
                assert any(n.get('content-desc') == 'Switch to front camera' for n in ui_nodes), 'A001 rear camera required'
        assert target('cat ' + CON + 'panelDC', root=True) == '0'
        assert target('cat ' + CON + 'mipi_cmd_log_en', root=True).endswith(': 0')
        target(f'test ! -e {TMP} && test ! -e {TRACE}', root=True)
        assert 'pwm_mode/' not in target('cat /sys/kernel/tracing/kprobe_events', root=True, private='prior-probes.txt')
        before = {k: target('settings get system ' + k) for k in keys}
        before['bl_power'] = target('cat ' + BL + 'bl_power', root=True)
        if short_read_control:
            before['native_dbv'] = int(target('cat ' + BL + 'brightness', root=True))
        assert before['bl_power'] in ('0', '4')
        if coupled_on and not owner_return:
            assert before['bl_power'] == '0' and before['screen_brightness_mode'] == '0', 'S0C1 requires awake/manual preflight'
        if owner_return:
            report['before_return'] = before
            before = view_report['before']
        report['before'] = before
        target(f'mkdir -m 700 {TMP}; mkdir {TMP}/debugfs')
        tmp_created = True
        if short_read_control:
            assert esd_mode() == 'reg_read', 'Native ESD must be restored before this experiment'
        adb_run(['adb', '-t', str(transports['target']), 'push', str(chunks_dir), TMP + '/'],
                       check=True, capture_output=True, timeout=25)
        for path in chunks_dir.iterdir():
            actual = target('sha256sum ' + TMP + '/chunks/' + path.name).split()[0]
            assert actual == hashlib.sha256(path.read_bytes()).hexdigest()
        target('mkdir ' + TRACE, root=True)
        instance_created = True
        target(f"printf '0\\n' > {TRACE}/tracing_on; printf 'mono\\n' > {TRACE}/trace_clock", root=True)
        for name, definition in PROBES.items():
            target("printf '%s\\n' " + shlex.quote(definition) + ' >> /sys/kernel/tracing/kprobe_events', root=True)
            created_probes.append(name)
            target(f"printf '1\\n' > {TRACE}/events/pwm_mode/{name}/enable", root=True)
        target(f"printf '1\\n' > {TRACE}/tracing_on", root=True)
        if reproduction:
            enable_logger()  # Observe native HOME/Settings/redraw transitions, not only later tables.
            report['logger_enabled_before_setup'] = True
            save()
        settings_changed = True
        if reproduction:
            target('settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; settings put system screen_off_timeout 600000; input keyevent 224')
        else:
            target('settings put system screen_brightness_mode 0; settings put system screen_brightness 52; settings put system min_refresh_rate 120.0; settings put system peak_refresh_rate 120.0; settings put system screen_off_timeout 600000; input keyevent 224')
        wait_target("dumpsys window policy | grep -F 'screenState='", 'screenState=SCREEN_STATE_ON')
        wait_target("dumpsys window policy | grep -F 'interactiveState='", 'interactiveState=INTERACTIVE_STATE_AWAKE')
        target('wm dismiss-keyguard')
        wait_target("dumpsys window policy | grep -F 'mIsShowing='", 'mIsShowing=false')
        if short_read_control:
            # WAKEUP on an already-awake phone did not reset dimmed user activity.
            # HOME + explicit Settings launch was independently observed to restore DBV3584.
            target('input keyevent 3')
        target('am start -W --activity-clear-top -n ' + shlex.quote('com.android.settings/.Settings$DisplaySettingsActivity'))
        if not owner_return and not reproduction:
            wait_target('cat ' + BL + 'brightness', '3584')
        display = target('dumpsys display', private='target-display.txt')
        assert re.search(r'mActiveSfDisplayMode=[^\n]*peakRefreshRate=120\.', display)
        target("printf '%s\\n' " + str(trial_dbv) + " > " + BL + 'brightness', root=True)
        wait_target('cat ' + BL + 'brightness', str(trial_dbv))
        if redraw_control or blocks_redraw:
            repaint_settings('preflight')  # Setup only; measured phases retain strict redraw audit.
        if not reproduction:
            enable_logger()
        else:
            create_stock_anchor()
        if not manual_session:
            if coupled_9d:
                camera_files_before = shell('camera', "find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'",
                                            private='camera-files-before.txt')
            else:
                report['media_since_epoch'] = int(time.time()) - 2
            recording = True
            camera_tap('Start recording video')
            assert any(n.get('content-desc') == 'Stop recording video' for n in camera_ui().iter('node'))
        if reproduction:
            report['recording_preflight'] = [camera_metadata('recording-preflight-1')]
            time.sleep(.2)
            report['recording_preflight'].append(camera_metadata('recording-preflight-2'))
            save()
            # Independent bounded recovery never writes a DSI table into an unknown queue.
            # The owner separately approves this ordinary reboot even on host/tunnel loss.
            watchdog = f'sleep 600; if test -d {TMP}/watchdog_armed; then /system/bin/reboot; fi'
            target(f'set -e; mkdir {TMP}/watchdog_armed; nohup /system/bin/sh -c ' + shlex.quote(watchdog) +
                   f' >{TMP}/watchdog.log 2>&1 </dev/null & echo $! >{TMP}/watchdog.pid', root=True)
            target(f'test -d {TMP}/watchdog_armed; kill -0 $(cat {TMP}/watchdog.pid)', root=True)
            report['watchdog_armed'] = True
            save()
        for label, name in stages:
            apply_program(label, name, programs[name])
            if redraw_control and name == 'native_on':
                observe_redraw()
        report['stock_return_verified'] = not owner_view
        if reproduction:
            assert esd_mode() == 'reg_read'
            target(f'rmdir {TMP}/watchdog_armed', root=True)
            report['watchdog_disarmed_after_stock_return'] = True
        profile = target('cat /sys/kernel/tracing/kprobe_profile', root=True, private='probe-profile.txt')
        for name in PROBES:
            rows = re.findall(r'^\s*' + name + r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
            assert len(rows) == 1 and int(rows[0][1]) == 0, (name, rows)
        if manual_session:
            report['owner_view_active'] = owner_view
            report['manual_session_part_complete'] = True
        else:
            report['redraw_control_complete' if redraw_control else 'series_complete' if blocks or coupled_on else 'three_stages_complete'] = True
    except BaseException as error:
        if reproduction:
            failure = private_dir / 'failure.txt'
            failure.write_text(type(error).__name__ + ': ' + str(error) + '\n')
            failure.chmod(0o600)
        report['error'] = type(error).__name__ + (': private details withheld' if reproduction else ': ' + str(error))
        save()
        if pending_uncertain or candidate_active:
            try:
                target('cat ' + TRACE + '/trace', root=True, private='error-trace.txt', timeout=5)
                target('dmesg', root=True, private='error-kernel.txt', timeout=5)
            except Exception:
                pass
            try:
                recover_reboot()
            except Exception as recovery_error:
                report['recovery_error'] = type(recovery_error).__name__ if reproduction else str(recovery_error)
                save()
    finally:
        errors = []
        if reproduction and not pending_uncertain and not candidate_active:
            try:
                # Also covers an uncertain watchdog launch before the first table.
                # Never disarm while panel/queue recovery is still uncertain.
                if tmp_created:
                    target(f'if test -d {TMP}/watchdog_armed; then rmdir {TMP}/watchdog_armed; fi; test ! -e {TMP}/watchdog_armed', root=True)
                    report['watchdog_disarmed_no_pending_candidate'] = True
            except Exception as error:
                errors.append('Watchdog disarm: ' + str(error))
        if recording:
            try:
                if any(n.get('content-desc') == 'Stop recording video' for n in camera_ui().iter('node')):
                    camera_tap('Stop recording video')
                assert any(n.get('content-desc') == 'Start recording video' for n in camera_ui().iter('node'))
                report['camera_stopped_verified'] = True
            except Exception as error:
                errors.append('Recorder: ' + str(error))
        if not report.get('recovery_error'):
            if short_read_control and reader_started:
                try:
                    # Independent recovery after host/read interruption; never append to an uncertain batch.
                    assert not pending_uncertain
                    from check_ddic_stock_latch import reader
                    text = target(reader(restore_only=True, mount_dir=TMP + '/debugfs'), root=True, private='esd-final.txt')
                    assert 'ESD_RESTORED reg_read' in text and esd_mode() == 'reg_read'
                    report['esd_restored'] = True
                except Exception as error:
                    errors.append('ESD recovery: ' + str(error))
            if logger_on:
                try:
                    target("printf '0\\n' > " + CON + 'mipi_cmd_log_en', root=True)
                except Exception as error:
                    errors.append('Logger: ' + str(error))
            if instance_created:
                try:
                    target(f"printf '0\\n' > {TRACE}/tracing_on", root=True)
                    target('cat ' + TRACE + '/trace', root=True, private='trace-final.txt')
                    for name in created_probes:
                        target(f"printf '0\\n' > {TRACE}/events/pwm_mode/{name}/enable", root=True)
                    target('rmdir ' + TRACE, root=True)
                except Exception as error:
                    errors.append('Trace instance: ' + str(error))
            for name in reversed(created_probes):
                try:
                    target("printf '%s\\n' " + shlex.quote('-:pwm_mode/' + name) + ' >> /sys/kernel/tracing/kprobe_events', root=True)
                except Exception as error:
                    errors.append('Probe: ' + str(error))
            if settings_changed and not report.get('owner_view_active'):
                try:
                    restore_keys = ('screen_brightness', 'min_refresh_rate', 'peak_refresh_rate', 'screen_off_timeout', 'screen_brightness_mode')
                    if reproduction:
                        from dsi_trial_transaction import refresh_restore_order
                        current_peak = target('settings get system peak_refresh_rate')
                        rates = refresh_restore_order(before['min_refresh_rate'], current_peak)
                        restore_keys = ('screen_brightness', *rates, 'screen_off_timeout', 'screen_brightness_mode')
                    for key in restore_keys:
                        target('settings delete system ' + key if before[key] == 'null'
                                else 'settings put system ' + key + ' ' + shlex.quote(before[key]))
                    if short_read_control and before['screen_brightness_mode'] == '0' and before['bl_power'] == '0':
                        # A same-value Android settings write need not undo the direct sysfs override.
                        target("printf '%s\\n' " + str(before['native_dbv']) + ' > ' + BL + 'brightness', root=True)
                        wait_target('cat ' + BL + 'brightness', str(before['native_dbv']))
                    if before['bl_power'] == '4':
                        target('input keyevent 223')
                    wait_target('cat ' + BL + 'bl_power', before['bl_power'])
                    after = {k: target('settings get system ' + k) for k in keys}
                    after['dc'] = target('cat ' + CON + 'panelDC', root=True)
                    after['logger'] = target('cat ' + CON + 'mipi_cmd_log_en', root=True)
                    after['selinux'] = target('getenforce')
                    if short_read_control:
                        after['native_dbv'] = int(target('cat ' + BL + 'brightness', root=True))
                        if before['screen_brightness_mode'] == '0' and before['bl_power'] == '0':
                            assert after['native_dbv'] == before['native_dbv']
                    assert all(after[k] == before[k] for k in keys if k != 'screen_brightness')
                    if before['screen_brightness_mode'] == '0':
                        assert after['screen_brightness'] == before['screen_brightness']
                    assert after['dc'] == '0' and after['logger'].endswith(': 0') and after['selinux'] == 'Enforcing'
                    report.update(target_restored=True, after=after)
                except Exception as error:
                    errors.append('Target settings: ' + str(error))
            if tmp_created:
                try:
                    if reproduction:
                        assert report.get('watchdog_disarmed_no_pending_candidate'), 'Preserve watchdog evidence until disarm verified'
                        target(f'rm -f {TMP}/watchdog.log {TMP}/watchdog.pid {TMP}/transaction_trace', root=True)
                    paths = ' '.join(TMP + '/chunks/' + p.name for p in chunks_dir.iterdir())
                    if redraw_control or blocks_redraw:
                        target('rm -f ' + TMP + '/redraw-ui.xml')
                    target('rm ' + paths + f'; rmdir {TMP}/chunks {TMP}/debugfs {TMP}')
                    report['temporary_device_files_removed'] = True
                except Exception as error:
                    errors.append('Temporary files: ' + str(error))
        if report.get('camera_stopped_verified'):
            try:
                if coupled_9d:
                    camera_files_after = shell('camera', "find /sdcard/DCIM/OpenCamera -maxdepth 1 -type f -name '*.mp4'",
                                               private='camera-files-after.txt')
                    source = new_camera_video(camera_files_before, camera_files_after)
                    size = int(shell('camera', 'stat -c %s ' + shlex.quote(source)))
                    assert size > 0
                else:
                    query = shell('camera', 'content query --uri content://media/external/video/media --projection _id:_data:_size:duration:date_added --where ' + shlex.quote('date_added>=' + str(report['media_since_epoch'])))
                    rows = re.findall(r'_data=(/storage/emulated/0/DCIM/OpenCamera/VID_\d+_\d+\.mp4), _size=(\d+), duration=(\d+), date_added=(\d+)', query)
                    assert len(rows) == 1
                    source, size, duration, _ = rows[0]
                dest = ROOT / ('artifacts/optical/pacman_dsi_blocks_20261106.mp4' if blocks
                               else 'artifacts/optical/pacman_dsi_mode90_20261106.mp4')
                if blocks_redraw:
                    dest = ROOT / 'artifacts/optical/pacman_dsi_blocks_redraw_20261106.mp4'
                if selector_split:
                    dest = ROOT / 'artifacts/optical/pacman_dsi_selector_split_20261107.mp4'
                if coupled_on:
                    dest = ROOT / 'artifacts/optical/pacman_dsi_coupled_on_20261107.mp4'
                    if coupled_9d:
                        dest = ROOT / 'artifacts/optical/a001_dsi_coupled_9d_20261108.mp4'
                if stock_control:
                    dest = ROOT / ('artifacts/optical/pacman_dsi_stock_on_dbv_20261106.mp4' if replay_dbv
                                    else 'artifacts/optical/pacman_dsi_stock_on_20261106.mp4')
                if redraw_control:
                    dest = ROOT / 'artifacts/optical/pacman_dsi_stock_on_redraw_20261106.mp4'
                if reproduction:
                    dest = private_dir / (config.experiment_id + '.mp4')
                assert not dest.exists()
                adb_run(['adb', '-t', str(transports['camera']), 'pull', source, str(dest)],
                               check=True, capture_output=True, timeout=100)
                dest.chmod(0o600)
                assert dest.stat().st_size == int(size)
                if coupled_9d:
                    probe = json.loads(subprocess.check_output([
                        'ffprobe', '-v', 'error', '-show_entries',
                        'stream=codec_type,codec_name,width,height:format=duration',
                        '-of', 'json', str(dest)], text=True, timeout=15))
                    assert len(probe['streams']) == 1 and probe['streams'][0]['codec_type'] == 'video'
                    assert probe['streams'][0]['codec_name'] == 'h264'
                    assert (probe['streams'][0]['width'], probe['streams'][0]['height']) == (1280, 720)
                    duration = round(float(probe['format']['duration']) * 1000)
                    assert duration > 0
                report.update(video=('<private video>' if reproduction else str(dest.relative_to(ROOT))), video_bytes=int(size), duration_ms=int(duration))
            except Exception as error:
                errors.append('Video acquisition: ' + str(error))
        if owner_view and report.get('owner_view_active'):
            try:
                state()
                assert target('cat ' + CON + 'mipi_cmd_log_en', root=True).endswith(': 0')
                assert report.get('esd_restored') and report.get('temporary_device_files_removed') and not errors
                report['owner_view_ready_at_utc'] = now()
                report['target_restored'] = False  # Intentional live handoff; never claim stock restoration.
            except Exception as error:
                errors.append('Owner view handoff: ' + str(error))
                try:
                    recover_reboot()
                    report['owner_view_active'] = False
                except Exception as recovery_error:
                    report['recovery_error'] = type(recovery_error).__name__ if reproduction else str(recovery_error)
        if reproduction and lock_acquired and not pending_uncertain and not candidate_active and not errors and not report.get('recovery_error'):
            try:
                target(lock_ops['release'], root=True)
                report['exclusive_device_lock_released'] = True
            except Exception as error:
                errors.append('Device lock: ' + str(error))
        report.update(cleanup_errors=([e.split(':', 1)[0] + ': private details withheld' for e in errors] if reproduction else errors), finished_at_utc=now())
        save()
    print(json.dumps({k: v for k, v in report.items() if k not in ('events', 'authorization')}, indent=2), flush=True)
    if report.get('error') or report.get('recovery_error') or report['cleanup_errors']:
        raise SystemExit(1)


def now():
    return datetime.now(timezone.utc).isoformat()


if __name__ == '__main__':
    main()
