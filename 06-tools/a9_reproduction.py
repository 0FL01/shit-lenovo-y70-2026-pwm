"""Fresh one-shot A9-only reproduction planning; no device I/O at import."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex


LOCK = '/data/local/tmp/legion-pwm-research.lock'
C1_SCOPE = {'page': 0x23, 'opcode': 0xc1, 'length': 3,
            'stages': ['stock', 'a9_only', 'stock'], 'refresh_hz': 120,
            'position': 'after_selector_readback_before_hold',
            'framing': 'dcs_long3_wc3_ecc_count9_scratch16', 'read_only': True}


def lock_commands(token):
    """Own exactly this root mutex token; never steal or delete stale ownership."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]{8,128}', token):
        raise ValueError('Invalid lock token')
    q = shlex.quote
    verify = (f'test ! -L {LOCK}; test -d {LOCK}; '
              f'test "$(stat -c %u {LOCK})" = 0; test "$(stat -c %a {LOCK})" = 700; '
              f'test ! -L {LOCK}/owner; test -f {LOCK}/owner; '
              f'test "$(stat -c %u {LOCK}/owner)" = 0; test "$(stat -c %a {LOCK}/owner)" = 600; '
              f'test "$(cat {LOCK}/owner)" = {q(token)}')
    return {
        'acquire': f'set -eu; umask 077; mkdir -m 700 {LOCK}; printf %s {q(token)} > {LOCK}/owner; chmod 600 {LOCK}/owner; ' + verify,
        'verify': 'set -eu; ' + verify,
        'release': 'set -eu; ' + verify + f'; rm {LOCK}/owner; rmdir {LOCK}',
    }


def validate_c1_trace(before, after, entry_count):
    """Account actual main trace deltas, including the read and all page writes."""
    def records(text):
        if 'LOST' in text or re.search(r'\brc=-\d+', text):
            raise ValueError('Lost/failed main trace during C1')
        entries = [tuple(map(int, row)) for row in re.findall(
            r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)', text)]
        returns = list(map(int, re.findall(r'\bmode_return:.*?rc=(-?\d+)', text)))
        controls = list(map(int, re.findall(r'\bmode_ctrl_return:.*?rc=(-?\d+)', text)))
        return entries, returns, controls
    # Trace metadata headers may change counts; every prior event line must not.
    event_pattern = re.compile(r'\bmode_(?:entry|return|ctrl_return):')
    old_lines = [line for line in before.splitlines() if event_pattern.search(line)]
    new_lines = [line for line in after.splitlines() if event_pattern.search(line)]
    if new_lines[:len(old_lines)] != old_lines:
        raise ValueError('Main trace event prefix changed during C1')
    old, new = records(before), records(after)
    if len(old[0]) != entry_count or len(old[1]) != entry_count:
        raise ValueError('Main trace count before C1 changed')
    if any(new[i][:len(old[i])] != old[i] for i in range(3)):
        raise ValueError('Main trace prefix changed during C1')
    delta = [new[i][len(old[i]):] for i in range(3)]
    if delta[0] != [(0, 11, 0)] * 3 or delta[1] != [0] * 3:
        raise ValueError('Expected exactly three standalone C1 page callbacks')
    background = []
    controls = delta[2]
    if controls != [0, 3, 0, 0]:
        # ESD is restored by the qualified child before the host reads main trace.
        # Classify only the exact observed native ESD caller outside the C1 window.
        parsed = []
        line_pattern = re.compile(
            r'^\s*(.+)-(\d+)\s+(?:\([^)]*\)\s+)?\[\d+\]\s+\S+\s+'
            r'(\d+\.\d+):\s+(mode_entry|mode_return|mode_ctrl_return):\s+(.*)$')
        for line in new_lines[len(old_lines):]:
            match = line_pattern.fullmatch(line)
            if match is None:
                raise ValueError('Cannot qualify extra controller event without task/time/callsite')
            task, pid, timestamp, event, payload = match.groups()
            parsed.append((task.strip(), int(pid), float(timestamp), event, payload))
        if any(a[2] > b[2] for a, b in zip(parsed, parsed[1:])):
            raise ValueError('Main trace timestamps out of order')
        starts = [record[2] for record in parsed if record[3] == 'mode_entry']
        ends = [record[2] for record in parsed if record[3] == 'mode_return']
        if len(starts) != 3 or len(ends) != 3 or starts[0] >= ends[-1]:
            raise ValueError('Unqualified C1 callback window')
        lower, upper = starts[0], ends[-1]
        controls = []
        esd_call = '(dsi_display_validate_status+0x154/0x308 [msm_drm] <- dsi_ctrl_cmd_transfer) rc=1'
        for task, pid, timestamp, event, payload in parsed:
            if event != 'mode_ctrl_return':
                continue
            rc_match = re.search(r'\brc=(-?\d+)$', payload)
            if rc_match is None:
                raise ValueError('Unqualified controller return')
            rc = int(rc_match[1])
            if rc == 1:
                if (not re.fullmatch(r'kworker/\d+:\d+', task) or payload != esd_call
                        or lower <= timestamp <= upper):
                    raise ValueError('Unexpected ESD/controller event inside or outside C1 window')
                background.append({'kind': ('native_esd_resumed_after_restoration' if timestamp > upper
                                             else 'native_esd_before_c1_window'),
                                   'caller': 'dsi_display_validate_status+0x154/0x308',
                                   'return_code': 1, 'timestamp': timestamp})
            else:
                if not lower <= timestamp <= upper:
                    raise ValueError('C1 controller return outside callback window')
                controls.append(rc)
        if controls != [0, 3, 0, 0]:
            raise ValueError('Expected page/read3/page/cleanup controller returns')
    return {'page_callbacks_verified': 3, 'controller_returns': controls,
            'background_esd': background, 'entry_count_after': len(new[0])}


def programs(root):
    if not __debug__:
        raise RuntimeError('Hardware checks require assertions enabled')
    panel = root / 'artifacts/device_tree/selected_boe_v4'
    stock = (panel / 'qcom,mdss-dsi-dc-off-command').read_bytes()
    native = (panel / 'qcom,mdss-dsi-dc-on-command').read_bytes()
    from inspect_cn_dtbo import packets
    parsed = packets(stock)
    if len(stock) != 875 or len(native) != 875 or len(parsed) != 75:
        raise ValueError('Unexpected native tables')
    packet = parsed[6]
    if (packet['page'], packet['offset_in_property'] + 8, packet['payload_hex']) != (0x23, 68, 'a9 0e'):
        raise ValueError('A9 provenance changed')
    if stock[68] != 0x0e or native[68] != 0x8e:
        raise ValueError('Native selector bytes changed')
    if hashlib.sha256(stock).hexdigest() != 'b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193':
        raise ValueError('Pinned stock table changed')
    if hashlib.sha256(native).hexdigest() != '4c1fc1807aadb63b54efab3cc7baa2c81f7a0107e81bd85dd35db16190fe7c33':
        raise ValueError('Pinned native ON provenance changed')
    candidate = bytearray(stock)
    candidate[68] = native[68]
    return {'stock': stock, 'a9_only': bytes(candidate)}


def verify_redraw_interval(text, marker, label):
    """Accept a frame-only chooser redraw, never a hidden native DSI change."""
    begin, end = marker + '_REDRAW_BEGIN_' + label, marker + '_REDRAW_END_' + label
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError('Missing or duplicated redraw audit markers')
    start, finish = text.index(begin), text.index(end)
    if finish <= start:
        raise ValueError('Redraw audit markers out of order')
    section = text[start + len(begin):finish]
    if re.search(r'\bdsi_ctrl_cmd_transfer\b', section) or 'Command transfer failed' in section:
        raise ValueError('Native DSI activity during chooser redraw; optical stage invalid')
    return {'method': 'native_timeout_chooser_open_cancel',
            'native_dsi_writes': 0, 'marker_interval_verified': True}


def prepare(root, argv):
    parser = argparse.ArgumentParser(description='Fresh stock → A9-only → stock, one continuous A001 video')
    parser.add_argument('target', type=int)
    parser.add_argument('camera', type=int)
    parser.add_argument('--experiment-id', required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dbv', type=int, required=True)
    parser.add_argument('--offline-check', action='store_true')
    parser.add_argument('--capture-c1', action='store_true')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[a-z][a-z0-9_]{7,63}', args.experiment_id):
        raise ValueError('Use a fresh lowercase experiment ID (8–64 characters)')
    if args.target <= 0 or args.camera <= 0 or args.target == args.camera:
        raise ValueError('Two distinct positive transport IDs required')
    if not 1 <= args.dbv <= 16180:
        raise ValueError('Invalid native DBV')
    out = args.output.resolve()
    if not out.is_relative_to((root / 'artifacts').resolve()):
        raise ValueError('Output must be a NEW directory under repository artifacts')
    if out.exists():
        raise ValueError('Output already exists; one-shot only')
    data = programs(root)
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in data.items()}
    auth = json.loads(args.authorization.read_text())
    required = dict(experiment_id=args.experiment_id, mode='a9_reproduction',
                    sequence=['stock', 'a9_only', 'stock'], candidates=['a9_only'],
                    program_sha256=hashes, native_dbv=args.dbv,
                    output=str(out.relative_to(root)), emergency_reboot_approved=True,
                    watchdog_reboot_approved=True, watchdog_seconds=600,
                    camera_profile='A001_Galaga_OpenCamera_1.56.2_720p_h264_no_audio_100us_iso6400')
    if args.capture_c1:
        required['c1_capture'] = C1_SCOPE
        if json.dumps(auth.get('c1_capture'), sort_keys=True) != json.dumps(C1_SCOPE, sort_keys=True):
            raise ValueError('Exact optional C1 capture scope required')
    elif 'c1_capture' in auth:
        raise ValueError('C1 scope present without --capture-c1')
    if any(auth.get(k) != v or type(auth.get(k)) is not type(v) for k, v in required.items()):
        raise ValueError('Fresh exact experiment, output, byte hashes, DBV, camera and recovery authorization required')
    if not isinstance(auth.get('owner_confirmation'), str) or not auth['owner_confirmation'].strip():
        raise ValueError('Actual owner confirmation required, never synthesized by runner')
    approved = datetime.fromisoformat(auth.get('approved_at_utc', ''))
    if approved.tzinfo is None or approved > datetime.now(timezone.utc):
        raise ValueError('Approval timestamp must be timezone-aware and not in the future')
    private = Path.home() / '.cache/legion-y70-trials' / args.experiment_id
    if private.exists():
        raise ValueError('Experiment ID already consumed on this host')
    return args, out, private, data, required
