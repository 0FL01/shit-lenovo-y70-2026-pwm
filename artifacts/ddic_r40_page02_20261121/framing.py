#!/usr/bin/env python3
"""Offline R40 framing gate: python3 framing.py RAW NONCE -> sanitized JSON.

RAW is one operation: a DATA line outside the trace and profile blocks, the
formatted tracefs trace (including its entries-in-buffer/entries-written row),
then the four filtered kprobe_profile rows. Also accepts probe.py's complete
NONCE ... R40_OK envelope. 0=qualified, 1=rejected, 2=I/O or usage error.
transport_verified describes the native return sequence only; it
does not attest selector bytes, ESD restoration, or operator/target state.
"""
import json
from pathlib import Path
import re
import sys

# Import only the offline probe schema / ECC; leave no bytecode in the worktree.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '06-tools'))
_no_pyc = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    from capture_ddic_85 import ecc, probe_specs
finally:
    sys.path.pop(0)
    sys.dont_write_bytecode = _no_pyc


LIMIT = 128 * 1024
ORDER = ('ctrl', 'tx', 'hardware', 'header', 'ctrl', 'ctrl', 'tx')
MARKERS = ('TRACE_BEGIN', 'TRACE_END', 'PROFILE_BEGIN', 'PROFILE_END')
ENTRY_COUNT = re.compile(r'# entries-in-buffer/entries-written:\s*(\d+)/(\d+)\s+#P:[1-9]\d*')
TRACE_ROW = re.compile(
    r'\s*[\w.:/+~-]+-(?P<pid>[1-9][0-9]*)\s+(?:\(\s*(?:\d+|-+)\s*\)\s+)?\[[0-9]+\]\s+'
    r'\S+\s+(?P<time>[0-9]+\.[0-9]+):\s+(?P<name>\w+):\s+'
    r'\((?P<site>[^()]+)\)\s+(?P<fields>.+)', re.ASCII)
# Actual formatted sites of the pinned module. In particular a controller
# return from an unrelated read must not stand in for the candidate's RX.
WRITE = 'dsi_host_transfer_sub+0x2f4/0x558 [msm_drm] <- dsi_ctrl_cmd_transfer'
RX = 'dsi_display_cmd_receive+0x448/0x4e8 [msm_drm] <- dsi_ctrl_cmd_transfer'
TX = '_sde_debugfs_conn_cmd_tx_write+0x3ac/0x4d8 [msm_drm] <- dsi_display_cmd_transfer'
SITES = (WRITE, TX, 'dsi_ctrl_hw_cmn_get_cmd_read_data+0x5c/0x350 [msm_drm]',
         'dsi_ctrl_cmd_transfer+0x494/0x86c [msm_drm]', RX, WRITE, TX)


class Rejected(ValueError):
    """Only constant, public reason codes belong here."""


def require(condition, code):
    if not condition:
        raise Rejected(code)


def result():
    return dict(status='rejected', reason=None, transport_verified=False,
                framing_qualified=False, value=None, header_hex=None,
                raw_hardware_count=None, normalized_count=None, returned=None,
                data_length=None, ctrl_returns=None, tx_returns=None, profile=None)


def sections(text, nonce):
    lines = text.split('\n')
    require([s for s in lines if s in MARKERS] == list(MARKERS), 'block_boundaries')
    tb, te, pb, pe = map(lines.index, MARKERS)
    before, between, after = ([s for s in region if s.strip()]
                              for region in (lines[:tb], lines[te+1:pb], lines[pe+1:]))
    if before and before[0].startswith('NONCE '):
        require(before[0] == 'NONCE ' + nonce and len(before) == 2 and not between
                and len(after) == 1 and re.fullmatch(
                    r'R40_OK action=(?:fe|[ab](?:80|82|ba)) epoch=\d+ page=0 esd=reg_read',
                    after[0], re.ASCII), 'candidate_envelope')
        outside = before[1:]
    else:
        outside = before + between + after
    require(len(outside) == 1 and re.fullmatch(r'DATA(?:[ \t]+0x[\da-fA-F]{1,2})+[ \t]*',
                                               outside[0], re.ASCII), 'data_record')
    return bytes(int(b, 16) for b in outside[0].split()[1:]), lines[tb+1:te], lines[pb+1:pe]


def fields(text, spec):
    """Parse the numeric fetchargs in their declared order and native widths."""
    schema = re.findall(r' (\w+)=\S+?:([usx])(32|64)(?= |$)', spec)
    tokens = text.split()
    require(schema and len(tokens) == len(schema), 'event_fields')
    out = {}
    for (key, kind, bits), token in zip(schema, tokens):
        # tracefs prints x32 in hex and signed/unsigned integers in decimal.
        pattern = {'x': r'0x[0-9a-fA-F]{1,8}', 'u': r'(?:0|[1-9]\d{0,19})',
                   's': r'(?:0|-?[1-9]\d{0,9})'}[kind]
        m = re.fullmatch(key + '=(' + pattern + ')', token, re.ASCII)
        require(m, 'event_fields')
        value = int(m[1], 0)
        width = int(bits) - (kind == 's')
        require((-(1 << width) if kind == 's' else 0) <= value < 1 << width, 'event_fields')
        out[key] = value
    return out


def parse_trace(lines, specs):
    rows, counts = [], []
    for line in lines:
        if line.startswith('#'):
            require(not rows, 'unexpected_trace_comment')
            if 'entries' in line:
                m = ENTRY_COUNT.fullmatch(line)
                require(m, 'trace_accounting')
                counts.append(m.groups())
            continue
        if not line.strip():
            continue
        m = TRACE_ROW.fullmatch(line)
        require(m and m['name'] in specs, 'unexpected_trace_record')
        name = m['name']
        sec, frac = m['time'].split('.')
        # Compare fractional timestamps without floating point rounding.
        stamp = int(sec), frac.rstrip('0')
        require(not rows or rows[-1][4] <= stamp, 'trace_time_order')
        rows.append((name.split('_')[0], m['pid'], m['site'],
                     fields(m['fields'], specs[name][1]), stamp))
    require(counts == [(str(len(rows)), str(len(rows)))], 'trace_accounting')
    return rows


def parse_profile(lines, specs):
    profile = {}
    for line in lines:
        if not line.strip():
            continue
        m = re.fullmatch(r'\s*(\w+)\s+(\d{1,20})\s+(\d{1,20})\s*', line, re.ASCII)
        require(m and m[1] in specs, 'unexpected_profile_record')
        kind = m[1].split('_')[0]
        require(kind not in profile, 'duplicate_profile_record')
        profile[kind] = dict(hits=int(m[2]), misses=int(m[3]))
    return profile


def validate(raw, nonce):
    """Consume bytes from a single saved transcript. Never return raw text."""
    out = result()
    try:
        require(re.fullmatch(r'[a-f0-9]{12}', nonce), 'invalid_nonce')
        require(len(raw) <= LIMIT, 'transcript_size')
        text = raw.decode('ascii').replace('\r\n', '\n')
        require(re.fullmatch(r'[\t\n -~]+', text), 'transcript_encoding')
        require(not re.search(r'\b(?:LOST|OVERRUN|DROPPED|RECOVERY_REQUIRED)\b', text, re.I),
                'trace_loss_or_recovery')
        _, specs = probe_specs(nonce)
        data, trace, profile = sections(text, nonce)
        out['data_length'] = len(data)
        rows = parse_trace(trace, specs)
        out['ctrl_returns'], out['tx_returns'] = (
            [f['rc'] for kind, _, _, f, _ in rows if kind == k] for k in ('ctrl', 'tx'))
        out['profile'] = parse_profile(profile, specs)
        require(tuple(r[0] for r in rows) == ORDER, 'operation_sequence')
        require(tuple(r[2] for r in rows) == SITES, 'unexpected_callsite')
        require(out['profile'] == {k: dict(hits=ORDER.count(k), misses=0) for k in set(ORDER)},
                'probe_accounting')
        pids = [r[1] for r in rows]
        require(pids[0] == pids[1] and pids[2] == pids[3] == pids[4] and pids[5] == pids[6],
                'uncorrelated_pid')
        hw, h = rows[2][3], rows[3][3]
        header = h['header'].to_bytes(4, 'little')
        rc = rows[4][3]['rc']
        out.update(header_hex=header.hex(' '), raw_hardware_count=hw['hw_status'] >> 16,
                   normalized_count=h['count'], returned=rc)
        require(out['tx_returns'] == [0, 0] and out['ctrl_returns'] == [0, rc, 0]
                and 1 <= rc <= 3, 'native_returns')
        require((h['requested'], h['allocation'], h['disp_op'], hw['read_bytes'], hw['mrps'])
                == (3, 16, 0, 16, 3), 'unexpected_rx_path')
        require(len(data) == rc, 'data_length_vs_return')
        out['transport_verified'] = True
        require(header[0] == 0x21, 'not_dcs_short1')
        require(rc == 1 and out['raw_hardware_count'] == h['count'] == 4, 'short1_counts')
        require(header[2] == 0 and header[3] == ecc(h['header'] & 0xffffff), 'reserved_or_ecc')
        require(header[1] == data[0], 'framed_byte_mismatch')
        out.update(status='qualified', framing_qualified=True, value=data[0])
    except Rejected as e:
        out['reason'] = str(e)
    except UnicodeDecodeError:
        out['reason'] = 'transcript_encoding'
    except ValueError:
        # Includes schema drift in the shared pinned probe definitions.
        out['reason'] = 'unrecognized_schema_or_number'
    return out


def main(argv):
    if len(argv) != 2:
        out = dict(result(), status='error', reason='usage_RAW_NONCE')
    else:
        try:
            with Path(argv[0]).open('rb') as f:
                out = validate(f.read(LIMIT + 1), argv[1])
        except OSError:
            out = dict(result(), status='error', reason='input_unreadable')
    print(json.dumps(out, sort_keys=True))
    return {'qualified': 0, 'rejected': 1, 'error': 2}[out['status']]


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
