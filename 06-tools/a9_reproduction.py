"""Fresh one-shot A9-only reproduction planning; no device I/O at import."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


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
