#!/usr/bin/env python3
"""One qualified page23:C1 read; no profile, DBV or refresh changes.

Exact saved msm_drm only. Request3 allocates16, MRPS3, one receive. A malformed
zero-length long response can still panic the stock parser. This tool cannot
repair that driver. It rejects CRC-contaminated short long-payloads via framing.
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

MODULE_SHA = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
LOCK = '/data/local/tmp/legion-pwm-research.lock'
PANEL = 'boe_ili97701A_682_1440x3168_dsc_cmd_v4'


def check(ok, message):
    if not ok:
        raise ValueError(message)


def ecc(header24):
    groups = ((0,1,2,4,5,7,10,11,13,16,20,21,22,23),
              (0,1,3,4,6,8,10,12,14,17,20,21,22,23),
              (0,2,3,5,6,9,11,12,15,18,20,21,22),
              (1,2,3,7,8,9,13,14,15,19,20,21,23),
              (4,5,6,7,8,9,16,17,18,19,20,22,23),
              (10,11,12,13,14,15,16,17,18,19,21,22,23))
    return sum((sum((header24 >> bit) & 1 for bit in group) & 1) << n
               for n, group in enumerate(groups))


def probe_specs(nonce):
    check(re.fullmatch(r'[a-f0-9]{12}', nonce), 'Invalid probe nonce')
    group = 'pwm_c1_' + nonce
    # All offsets are within the exact SHA-pinned .text symbols, NOT live VAs.
    return group, {
        'header_' + nonce: ('p', 'msm_drm:dsi_ctrl_cmd_transfer+0x494 '
            'header=+0(%x8):x32 requested=+0x18(%x20):u64 '
            'count=+0x2c($stack):u32 allocation=%x22:u64 '
            'disp_op=+0x648(%x28):u32'),
        'hardware_' + nonce: ('p', 'msm_drm:dsi_ctrl_hw_cmn_get_cmd_read_data+0x5c '
            'hw_status=%x0:x32 read_bytes=%x19:u32 mrps=%x23:u32'),
        'ctrl_' + nonce: ('r', 'msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32'),
        'tx_' + nonce: ('r', 'msm_drm:dsi_display_cmd_transfer rc=$retval:s32'),
    }


def reader_script(nonce, dbv, refresh, held_token=None):
    """Build bounded root shell. held_token joins, but never removes, a held lock.

    The lock contract is root-owned directory0700 plus root-owned0600 `owner`
    containing an ASCII token. Standalone owns it. Unknown/stale locks are never
    removed. Parent must not release an inherited lock until this returns clean.
    """
    check(1 <= dbv <= 16180 and refresh in (90,120,144), 'Invalid state guard')
    check(held_token is None or re.fullmatch(r'[A-Za-z0-9_.-]{8,128}', held_token), 'Invalid held token')
    group, specs = probe_specs(nonce)
    q = shlex.quote
    work = '/data/local/tmp/pwm-c1-' + nonce
    token = held_token or nonce
    lock_step = (f'[ "$(cat "$LOCK/owner")" = {q(token)} ]' if held_token else
                 f'mkdir -m 700 "$LOCK"\nowned=1\nprintf %s {q(token)} > "$LOCK/owner"\nchmod 600 "$LOCK/owner"')
    install = '\n'.join(f"printf '%s\\n' {q(kind+':'+group+'/'+name+' '+spec)} >> /sys/kernel/tracing/kprobe_events\nadded=\"$added {name}\""
                        for name, (kind, spec) in specs.items())
    body = f'''set -eu
umask 077
LOCK={q(LOCK)}
W={q(work)}
T=/sys/kernel/tracing/instances/{group}
G={group}
owned=0; mounted=0; traced=0; touched=0; made_work=0; added=''
cleanup() {{
 s=$?; trap - EXIT HUP INT TERM; set +e
 if [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then
   printf '%s' "$P0" > "$C/tx_cmd" || s=31
 fi
 if [ "$traced" = 1 ]; then printf 0 > "$T/tracing_on" || s=32; fi
 if [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then
   printf '%s\\n' reg_read > "$E" || s=33
   restored_esd=$(tr -d '\\000' < "$E")
   printf 'ESD_RESTORED %s\\n' "$restored_esd"
   [ "$restored_esd" = reg_read ] || s=34
 fi
 if [ "$traced" = 1 ]; then
   printf '\\nTRACE_BEGIN\\n'; cat "$T/trace" || s=35; printf 'TRACE_END\\n'
   printf 'PROFILE_BEGIN\\n'
   for e in $added; do grep -E "(^|[[:space:]])$e[[:space:]]" /sys/kernel/tracing/kprobe_profile || s=36; done
   printf 'PROFILE_END\\n'
   printf 0 > "$T/events/$G/enable" || s=37
 fi
 for e in $added; do printf '%s\\n' "-:$G/$e" >> /sys/kernel/tracing/kprobe_events || s=38; done
 if [ "$traced" = 1 ]; then rmdir "$T" || s=39; fi
 if [ "$mounted" = 1 ]; then umount "$W/dbg" || s=40; fi
 if [ "$made_work" = 1 ]; then rmdir "$W/dbg" "$W" || s=41; fi
 if [ "$s" = 0 ]; then
   if [ "$owned" = 1 ]; then
     [ "$(cat "$LOCK/owner")" = {q(token)} ] && rm "$LOCK/owner" && rmdir "$LOCK" || s=42
   fi
 fi
 if [ "$s" = 0 ]; then printf 'CLEANUP_OK\\n'; else printf 'RECOVERY_REQUIRED %s\\n' "$s"; fi
 exit "$s"
}}
trap cleanup EXIT
trap 'exit 30' HUP INT TERM
[ "$(id -u)" = 0 ]
{lock_step}
[ "$(stat -c %u "$LOCK")" = 0 ]
[ "$(stat -c %a "$LOCK")" = 700 ]
[ "$(stat -c %u "$LOCK/owner")" = 0 ]
[ "$(stat -c %a "$LOCK/owner")" = 600 ]
[ "$(getprop ro.boot.hardware.sku)" = XT2611-1 ]
[ "$(getprop ro.build.display.id)" = W3WWS36.65-64-4-1 ]
[ "$(getprop ro.boot.slot_suffix)" = _b ]
[ "$(uname -r)" = 6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k ]
[ "$(getenforce)" = Enforcing ]
[ "$(cat /sys/class/drm/card0-DSI-1/panelName)" = {PANEL} ]
[ "$(sha256sum /vendor/lib/modules/msm_drm.ko | cut -d ' ' -f 1)" = {MODULE_SHA} ]
[ "$(cat /sys/class/drm/card0-DSI-1/panelDC)" = 0 ]
[ "$(cat /sys/class/backlight/panel0-backlight/bl_power)" = 0 ]
[ "$(cat /sys/class/backlight/panel0-backlight/brightness)" = {dbv} ]
mode=$(dumpsys display | awk '/mActiveSfDisplayMode=/ && !seen++ {{sub(/.*peakRefreshRate=/, ""); sub(/[^0-9.].*/, ""); rate=$0}} END {{print rate}}')
awk -v f="$mode" 'BEGIN {{exit !(f>={refresh}-.03 && f<={refresh}+.03)}}'
printf 'STATE {dbv} %s\\n' "$mode"
mkdir -m 700 "$W"; made_work=1
mkdir -m 700 "$W/dbg"
mount -o rprivate none /
mount -t debugfs -o nosuid,nodev,noexec debugfs "$W/dbg"; mounted=1
C="$W/dbg/dri/9800000.qcom,mdss_mdp/DSI-1"
E="$W/dbg/qcom,mdss_dsi_mot_{PANEL}/esd_check_mode"
P0='0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0'
initial_esd=$(tr -d '\\000' < "$E")
printf 'ESD_INITIAL %s\\n' "$initial_esd"
[ "$initial_esd" = reg_read ]
[ ! -e "$T" ]
mkdir "$T"; traced=1
{install}
printf mono > "$T/trace_clock"
printf 128 > "$T/buffer_size_kb"
printf 1 > "$T/events/$G/enable"
touched=1
printf '%s\\n' esd_sw_sim_success > "$E"
active_esd=$(tr -d '\\000' < "$E")
printf 'ESD_ACTIVE %s\\n' "$active_esd"
[ "$active_esd" = esd_sw_sim_success ]
printf 1 > "$T/tracing_on"
printf '%s' '0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0x23' > "$C/tx_cmd"
printf '%s' '3 0x06 1 0 1 0 0 1 0xC1' > "$C/rx_cmd"
printf '%s' "$P0" > "$C/tx_cmd"
printf 'C1 '; cat "$C/rx_cmd"; printf '\\n'
[ "$(cat /sys/class/backlight/panel0-backlight/brightness)" = {dbv} ]
[ "$(cat /sys/class/backlight/panel0-backlight/bl_power)" = 0 ]
[ "$(getenforce)" = Enforcing ]
'''
    return 'timeout -k 3 30 unshare -m /system/bin/sh -c ' + q(body)


def validate_capture(stdout, nonce, dbv, refresh):
    """Fail closed. No claim about C1 semantics, writability, or PWM Hz."""
    check(stdout.count('CLEANUP_OK') == 1 and 'RECOVERY_REQUIRED' not in stdout, 'Unverified cleanup')
    for state,mode in [('INITIAL','reg_read'),('ACTIVE','esd_sw_sim_success'),('RESTORED','reg_read')]:
        check(re.findall(r'^ESD_'+state+r' (.+)$',stdout,re.M)==[mode], 'Unverified ESD '+state)
    check('LOST' not in stdout, 'Lost trace events')
    m = re.search(r'^STATE (\d+) ([0-9.]+)$', stdout, re.M)
    check(m and int(m[1]) == dbv and abs(float(m[2])-refresh)<.03, 'Unexpected display state')
    values = re.findall(r'^C1 ((?:0x[0-9a-fA-F]{1,2}\s*)+)$', stdout, re.M)
    check(len(values)==1, 'Missing/duplicate C1 output')
    data = [int(x,16) for x in values[0].split()]
    check(len(data)==3, 'C1 did not return exactly3 bytes')
    records = {}
    _, specs = probe_specs(nonce)
    for name in specs:
        records[name] = []
        for line in stdout.splitlines():
            if re.search(r'\b'+re.escape(name)+r':', line):
                pid = re.search(r'-(\d+)\s+(?:\(.*?\)\s+)?\[', line)
                fields = dict(re.findall(r'(\w+)=(0x[0-9a-fA-F]+|-?\d+)',line))
                check(pid is not None, 'Unrecognized trace PID format')
                records[name].append((int(pid[1]),{k:int(v,0) for k,v in fields.items()}))
    headers = records['header_'+nonce]
    check(len(headers)==1, 'Expected exactly one framed response')
    pid,h = headers[0]
    check(h.get('requested')==3 and h.get('allocation')==16 and h.get('disp_op')==0, 'Unexpected receive path')
    check(h.get('count')==9, 'Expected normalized long3 response count9')
    hw = records['hardware_'+nonce]
    check(len(hw)==1 and hw[0][0]==pid, 'Missing/ambiguous hardware count')
    raw=hw[0][1]
    check(raw.get('read_bytes')==16 and raw.get('mrps')==3, 'Unexpected helper width/MRPS')
    raw_count=raw.get('hw_status',0)>>16
    check(raw_count in (9,13), 'Unqualified raw hardware count')
    header=h.get('header',0)
    hb=header.to_bytes(4,'little')
    check(hb[0]==0x1c and int.from_bytes(hb[1:3],'little')==3, 'Not DCS long3: payload may contain CRC')
    check(hb[3]==ecc(header&0xffffff), 'Header ECC not qualified')
    # Android toybox printf can execute as a separate task for each write.
    # Correlate the read return with its header/helper task, but do not require
    # the page23/page0 writer tasks to share that PID.
    cr=[fields.get('rc') for p,fields in records['ctrl_'+nonce]]
    tx=[fields.get('rc') for p,fields in records['tx_'+nonce]]
    read_returns=[fields.get('rc') for p,fields in records['ctrl_'+nonce] if p==pid]
    check(read_returns.count(3)==1 and all(x in (0,3) for x in read_returns), 'Read-task return mismatch')
    check(cr==[0,3,0,0], 'Unexpected controller return sequence')
    check(tx==[0,0,0], 'Unexpected page-write return sequence')
    profile=stdout.split('PROFILE_BEGIN\n')[-1].split('PROFILE_END')[0]
    for name in specs:
        rows=re.findall(r'^\s*'+re.escape(name)+r'\s+(\d+)\s+(\d+)\s*$',profile,re.M)
        check(len(rows)==1 and int(rows[0][0])>0 and int(rows[0][1])==0, 'Probe misses/unqualified profile')
    return {'page':'23','opcode':'C1','requested':3,'data':data,'header_hex':hb.hex(' '),
            'raw_hardware_count':raw_count,'normalized_count':9,'scratch_allocation':16,
            'single_receive':True,'framing_qualified':True,'cleanup_verified':True,
            'native_dbv':dbv,'software_refresh':float(m[2]),'pwm_hz':None,
            'limit':'C1 semantics and writable behavior unknown; CRC payload itself not captured.'}


def capture(transport, nonce, dbv, refresh, held_token=None, evidence_dir=None):
    """Callable hook under caller-held root mutex, or standalone ownership."""
    from guarded_adb_socket import GuardedADB
    g=GuardedADB(); g.preflight(); g.bind(transport)
    command='su -c '+shlex.quote(reader_script(nonce,dbv,refresh,held_token))
    rc,out,err=g.shell(transport,command,40)
    text=out.decode(errors='replace')
    if evidence_dir is not None:
        for name, data in [('capture.txt',out),('stderr.txt',err)]:
            path=Path(evidence_dir)/name
            with path.open('xb') as f: f.write(data)
            path.chmod(0o600)
    if rc:
        raise RuntimeError('Device capture failed; cleanup/lock may require coordinator recovery')
    return validate_capture(text,nonce,dbv,refresh), text, err.decode(errors='replace')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('transport',type=int)
    p.add_argument('--dbv',type=int,required=True)
    p.add_argument('--refresh',type=int,choices=(90,120,144),required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--offline-check',action='store_true')
    a=p.parse_args()
    check(a.transport>0,'Positive bound transport required')
    check(not a.output.exists(),'Output exists; never silently repeat a capture')
    nonce=uuid.uuid4().hex[:12]
    reader_script(nonce,a.dbv,a.refresh)
    if a.offline_check:
        print('PASS offline: fixed3-byte C1 query, exact module probes, bounded cleanup; no device action')
        return
    # Reserve outcome before any external action, so an uncertain send is not retried.
    record={'started_at_utc':datetime.now(timezone.utc).isoformat(),'module_sha256':MODULE_SHA,
            'nonce':nonce,'physical_operation_attempted':False,'pwm_hz':None}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f: json.dump(record,f,indent=2)
    private=Path.home()/'.cache/legion-y70-c1'/nonce
    private.mkdir(parents=True,mode=0o700); os.chmod(private,0o700)
    try:
        record['physical_operation_attempted']=True
        result,out,err=capture(a.transport,nonce,a.dbv,a.refresh,evidence_dir=private)
        record.update(result)
    except Exception as e:
        record['error_type']=type(e).__name__
        record['status']='failed_or_uncertain; no retry; inspect private logs and root mutex'
        raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        a.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':
    main()
