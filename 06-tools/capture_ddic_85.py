#!/usr/bin/env python3
"""Qualified page23:85 observation, not a register setter.

Requests maximum3 for the audited16-byte scratch path, but accepts only an actual
DCS short1 response. No inferred register width, no profile/DBV/refresh changes.
Unexpected malformed long0 can still panic the stock driver before validation.
No device/network/process I/O at import or --offline-check.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import uuid

import capture_ddic_c1 as c1

MODULE_SHA = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
LOCK = c1.LOCK
check = c1.check
ecc = c1.ecc


def probe_specs(nonce):
    # Same exact ELF sites/register lifetimes; NOT the C1 response validator.
    check(c1.MODULE_SHA == MODULE_SHA, 'Module changed: re-audit short response path')
    _, specs = c1.probe_specs(nonce)
    expected = {
        'header_' + nonce: ('p', 'msm_drm:dsi_ctrl_cmd_transfer+0x494 '
            'header=+0(%x8):x32 requested=+0x18(%x20):u64 '
            'count=+0x2c($stack):u32 allocation=%x22:u64 '
            'disp_op=+0x648(%x28):u32'),
        'hardware_' + nonce: ('p', 'msm_drm:dsi_ctrl_hw_cmn_get_cmd_read_data+0x5c '
            'hw_status=%x0:x32 read_bytes=%x19:u32 mrps=%x23:u32'),
        'ctrl_' + nonce: ('r', 'msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32'),
        'tx_' + nonce: ('r', 'msm_drm:dsi_display_cmd_transfer rc=$retval:s32'),
    }
    check(specs == expected, 'Probe definitions changed: re-audit short response path')
    return 'pwm_85_' + nonce, specs


def reader_script(nonce, dbv, refresh, held_token=None):
    """Reuse the reviewed lifecycle shell, replacing only fixed query/labels.

    Fail closed if the C1 template changes unexpectedly. Existing C1 code and
    its callable interface are not modified. No arbitrary register argument.
    """
    parts = shlex.split(c1.reader_script(nonce, dbv, refresh, held_token))
    check(len(parts) == 9 and parts[:8] ==
          ['timeout','-k','3','30','unshare','-m','/system/bin/sh','-c'],
          'Changed lifecycle wrapper')
    script = parts[8]
    replacements = (
        ("'3 0x06 1 0 1 0 0 1 0xC1'", "'3 0x06 1 0 1 0 0 1 0x85'"),
        ("printf 'C1 '", "printf 'P85 '"),
        ('/data/local/tmp/pwm-c1-' + nonce, '/data/local/tmp/pwm-85-' + nonce),
    )
    for before, after in replacements:
        check(script.count(before) == 1, 'Changed lifecycle template: ' + before)
        script = script.replace(before, after)
    old, _ = c1.probe_specs(nonce)
    new, specs = probe_specs(nonce)
    check(script.count(old) == 2 + len(specs), 'Changed probe group template')
    return ' '.join(shlex.quote(x) for x in parts[:8]) + ' ' + shlex.quote(script.replace(old, new))


def validate_capture(stdout, nonce, dbv, refresh):
    """Qualify a real short1 response despite maximum receive request3."""
    check(stdout.count('CLEANUP_OK') == 1 and 'RECOVERY_REQUIRED' not in stdout,
          'Unverified cleanup')
    for state, mode in [('INITIAL','reg_read'), ('ACTIVE','esd_sw_sim_success'),
                        ('RESTORED','reg_read')]:
        check(re.findall(r'^ESD_' + state + r' (.+)$', stdout, re.M) == [mode],
              'Unverified ESD ' + state)
    check('LOST' not in stdout, 'Lost trace events')
    states = re.findall(r'^STATE (\d+) ([0-9.]+)$', stdout, re.M)
    check(len(states) == 1 and int(states[0][0]) == dbv and
          abs(float(states[0][1]) - refresh) < .03, 'Unexpected display state')
    values = re.findall(r'^P85 ((?:0x[0-9a-fA-F]{1,2}\s*)+)$', stdout, re.M)
    check(len(values) == 1, 'Missing/duplicate P85 output')
    data = [int(x, 16) for x in values[0].split()]
    check(len(data) == 1, 'P85 did not return exactly1 byte')
    check(stdout.count('TRACE_BEGIN\n') == stdout.count('TRACE_END\n') == 1,
          'Missing/ambiguous trace boundary')
    trace = stdout.split('TRACE_BEGIN\n')[1].split('TRACE_END\n')[0]
    records = {}
    _, specs = probe_specs(nonce)
    for name in specs:
        records[name] = []
        for line in trace.splitlines():
            if re.search(r'\b' + re.escape(name) + r':', line):
                pid = re.search(r'-(\d+)\s+(?:\(.*?\)\s+)?\[', line)
                fields = dict(re.findall(r'(\w+)=(0x[0-9a-fA-F]+|-?\d+)', line))
                check(pid is not None, 'Unrecognized trace PID format')
                records[name].append((int(pid[1]), {k:int(v,0) for k,v in fields.items()}))
    headers = records['header_' + nonce]
    check(len(headers) == 1, 'Expected exactly one framed response')
    pid, h = headers[0]
    check(h.get('requested') == 3 and h.get('allocation') == 16 and
          h.get('disp_op') == 0, 'Unexpected receive path')
    check(h.get('count') == 4, 'Expected normalized short response count4')
    hw = records['hardware_' + nonce]
    check(len(hw) == 1 and hw[0][0] == pid, 'Missing/ambiguous hardware count')
    raw = hw[0][1]
    check(raw.get('read_bytes') == 16 and raw.get('mrps') == 3,
          'Unexpected helper width/MRPS')
    raw_count = raw.get('hw_status', 0) >> 16
    # At MRPS3/width16 the helper strips4 only at raw13, not raw8.
    # An ACK-prefixed short response is deliberately not accepted here.
    check(raw_count == 4, 'Unqualified raw hardware count')
    header = h.get('header', 0)
    check(0 <= header <= 0xffffffff, 'Invalid header integer')
    hb = header.to_bytes(4, 'little')
    check(hb[0] == 0x21 and hb[2] == 0, 'Not DCS short1 with reserved byte0')
    check(hb[3] == ecc(header & 0xffffff), 'Header ECC not qualified')
    check(hb[1] == data[0], 'Printed payload differs from framed payload')
    cr = [fields.get('rc') for _,fields in records['ctrl_' + nonce]]
    tx = [fields.get('rc') for _,fields in records['tx_' + nonce]]
    read_returns = [fields.get('rc') for p,fields in records['ctrl_' + nonce] if p == pid]
    check(read_returns == [1], 'Read-task return mismatch')
    check(cr == [0,1,0,0], 'Unexpected controller return sequence')
    check(tx == [0,0,0], 'Unexpected page-write return sequence')
    check(stdout.count('PROFILE_BEGIN\n') == stdout.count('PROFILE_END\n') == 1,
          'Missing/ambiguous profile boundary')
    profile = stdout.split('PROFILE_BEGIN\n')[1].split('PROFILE_END\n')[0]
    for name in specs:
        rows = re.findall(r'^\s*' + re.escape(name) + r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
        check(len(rows) == 1 and int(rows[0][0]) > 0 and int(rows[0][1]) == 0,
              'Probe misses/unqualified profile')
    return {'page':'23', 'opcode':'85', 'requested_maximum':3, 'returned':1,
            'data':data, 'response_type':'DCS_short1', 'header_hex':hb.hex(' '),
            'raw_hardware_count':4, 'normalized_count':4, 'scratch_allocation':16,
            'single_receive':True, 'framing_qualified':True, 'cleanup_verified':True,
            'native_dbv':dbv, 'software_refresh':float(states[0][1]), 'pwm_hz':None,
            'limit':'Read-plane semantics and writability unknown; no control or Hz claim.'}


def capture(transport, nonce, dbv, refresh, held_token=None, evidence_dir=None):
    from guarded_adb_socket import GuardedADB
    g = GuardedADB(); g.preflight(); g.bind(transport)
    command = 'su -c ' + shlex.quote(reader_script(nonce, dbv, refresh, held_token))
    rc, out, err = g.shell(transport, command, 40)
    if evidence_dir is not None:
        for name, data in [('capture.txt',out), ('stderr.txt',err)]:
            path = Path(evidence_dir) / name
            with path.open('xb') as f: f.write(data)
            path.chmod(0o600)
    if rc:
        raise RuntimeError('Device capture failed; cleanup/lock may require coordinator recovery')
    text = out.decode(errors='replace')
    return validate_capture(text, nonce, dbv, refresh), text, err.decode(errors='replace')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('transport', type=int)
    p.add_argument('--dbv', type=int, required=True)
    p.add_argument('--refresh', type=int, choices=(90,120,144), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--offline-check', action='store_true')
    a = p.parse_args()
    check(a.transport > 0, 'Positive bound transport required')
    check(not a.output.exists(), 'Output exists; never silently repeat a capture')
    nonce = uuid.uuid4().hex[:12]
    reader_script(nonce, a.dbv, a.refresh)
    if a.offline_check:
        print('PASS offline: fixed P85 maximum3 query; accept actual DCS short1 only; no device action')
        return
    record = {'started_at_utc':datetime.now(timezone.utc).isoformat(), 'module_sha256':MODULE_SHA,
              'nonce':nonce, 'physical_operation_attempted':False, 'pwm_hz':None}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f: json.dump(record, f, indent=2)
    private = Path.home() / '.cache/legion-y70-p85' / nonce
    private.mkdir(parents=True, mode=0o700); os.chmod(private, 0o700)
    try:
        record['physical_operation_attempted'] = True
        result, _, _ = capture(a.transport, nonce, a.dbv, a.refresh, evidence_dir=private)
        record.update(result)
    except Exception as e:
        record['error_type'] = type(e).__name__
        record['status'] = 'failed_or_uncertain; no retry; inspect private logs and root mutex'
        raise
    finally:
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        a.output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
